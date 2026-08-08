"""发版验收：对着打好的包跑一遍核心链路。用完即删。"""
import re, sys, time
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/"
ok = []

def chk(name, cond, detail=""):
    ok.append((name, bool(cond), detail))
    print(("  PASS " if cond else "  FAIL ") + name + (f"  [{detail}]" if detail else ""))

def settle(p, ms=180000):
    end = time.time() + ms / 1000
    while time.time() < end:
        if p.locator(".progress-text, .wrap.generating").count() == 0:
            time.sleep(0.5)
            if p.locator(".progress-text, .wrap.generating").count() == 0:
                return
        time.sleep(0.5)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    p = b.new_page(viewport={"width": 1600, "height": 1000})
    errs = []
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    p.on("pageerror", lambda e: errs.append(str(e)))

    p.goto(URL, wait_until="load"); settle(p)
    chk("1 页面能打开", p.locator("#dv-chrome").count() == 1)
    chk("2 版本号 v1.4.5", "v1.4.5" in p.locator("#dv-chrome").inner_text())
    stats = p.locator("#dv-stats, .dv-stats").first.inner_text() if p.locator("#dv-stats, .dv-stats").count() else p.locator("body").inner_text()[:400]
    chk("3 引擎在线", "引擎 在线" in stats, stats.replace("\n", " ")[:60])
    tabs = [t.inner_text().strip() for t in p.get_by_role("tab").all()]
    chk("4 主导航齐全", len(tabs) >= 5, " / ".join(tabs))

    # 文生图：真出图
    p.get_by_role("tab", name=re.compile("文生图")).click(); settle(p)
    box = p.get_by_label("提示词", exact=False).first
    box.fill("一只橘猫坐在窗台上，午后阳光，胶片质感")
    p.locator("#dv-gen-btn button, #dv-gen-btn").first.click()
    imgs = p.locator("#dv-output img")
    end = time.time() + 300
    while time.time() < end and imgs.count() == 0:
        time.sleep(1)
    settle(p, 240000)
    chk("5 能真出图", imgs.count() >= 1,
        f"img={imgs.count()} status={p.locator('#dv-status').inner_text().strip()[:60]}")

    # 灵感库：首卡是「无灵感」占位，所以是 100+1
    p.get_by_role("tab", name=re.compile("提示词灵感")).click(); settle(p)
    insp = p.locator("#dv-br-inspo-gal .gallery-item")
    chk("6 灵感 100 条(+占位卡)", insp.count() == 101, f"count={insp.count()}")

    # 填入必须在文生图页验证：灵感浏览页按设计不回填
    p.get_by_role("tab", name=re.compile("文生图")).click(); settle(p)
    box = p.get_by_label("提示词", exact=False).first
    box.fill("XXX占位")
    cards2 = p.locator("#dv-inspo-cards .gallery-item")
    cards2.nth(2).click(); settle(p)
    filled = box.input_value()
    chk("7 灵感能填入提示词", filled != "XXX占位" and len(filled) > 10, filled[:40])

    # LoRA
    p.get_by_role("tab", name=re.compile("LoRA")).click(); settle(p)
    cards = p.locator("#dv-br-lora-gal .gallery-item")
    chk("8 LoRA 卡片正常", cards.count() > 10, f"count={cards.count()}")
    p.get_by_text("自建 / 编辑 LoRA", exact=True).click(); settle(p)
    cards.nth(4).click(); settle(p)
    cap = cards.nth(4).inner_text().strip().splitlines()[-1]
    sel = p.locator("#dv-lora-sel-hint b").inner_text().strip()
    chk("9 选中态与卡片一致", cap == sel, f"{cap} vs {sel}")
    chk("10 有刷新键与目录提示", p.get_by_role("button", name="刷新列表").count() == 1
        and "loras" in p.locator("#dv-lora-sel-hint").locator("xpath=..").inner_text().lower())
    before = cards.count()
    p.get_by_role("button", name="隐藏 / 取消隐藏选中").click(); settle(p)
    hid = cards.count()
    p.get_by_label("显示已隐藏").check(); settle(p)
    idx = next((i for i in range(cards.count())
                if cards.nth(i).inner_text().strip().splitlines()[-1] == cap), -1)
    cards.nth(idx).click(); settle(p)
    p.get_by_role("button", name="隐藏 / 取消隐藏选中").click(); settle(p)
    p.get_by_label("显示已隐藏").uncheck(); settle(p)
    chk("11 隐藏可往返", before == hid + 1 and cards.count() == before,
        f"{before}->{hid}->{cards.count()}")

    # 图库：老图还在 + 回填
    p.get_by_role("tab", name=re.compile("图库")).click(); settle(p)
    g = p.locator("#dv-hist-gallery .gallery-item, .gallery-item")
    chk("12 图库有图（含老用户旧图）", g.count() >= 2, f"count={g.count()}")

    chk("13 无 console 报错", not [e for e in errs if "favicon" not in e],
        str([e for e in errs if "favicon" not in e][:2]))
    p.screenshot(path="_dev_tools/_shot_release.png")
    b.close()

bad = [n for n, c, _ in ok if not c]
print("\n==== 结果:", f"{len(ok)-len(bad)}/{len(ok)} 通过", ("全部通过" if not bad else "未过: " + ", ".join(bad)))
sys.exit(1 if bad else 0)
