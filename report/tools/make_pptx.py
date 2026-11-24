"""Build slides.pptx: PowerPoint version of slides.pdf (same content),
with native charts and the Turkish talk track as speaker notes.

Usage: python make_pptx.py <summary.json> <out.pptx>
"""
import json
import pathlib
import sys

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

REPORT = pathlib.Path(__file__).resolve().parent.parent
ARCH = REPORT / "figures" / "fig_architecture_drawn.png"  # drawn by the student in draw.io

NAVY = RGBColor(0x1B, 0x26, 0x3B)
CONT = RGBColor(0x2A, 0x78, 0xB5)
CONT_L = RGBColor(0x7F, 0xB3, 0xDC)
VM = RGBColor(0xD9, 0x82, 0x2B)
VM_D = RGBColor(0x8C, 0x4A, 0x10)
INK = RGBColor(0x22, 0x2B, 0x36)
MUTED = RGBColor(0x5F, 0x6B, 0x7A)
TINT = RGBColor(0xEE, 0xF3, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
HEAD, BODY = "Cambria", "Calibri"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


# ------------------------------------------------------------------ helpers
def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def text(slide, x, y, w, h, parts, size=18, color=INK, font=BODY, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None):
    """parts: str or list of paragraphs; a paragraph is str or list of (text, opts) runs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    paras = parts if isinstance(parts, list) else [parts]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        runs = para if isinstance(para, list) else [(para, {})]
        for t, o in runs:
            r = p.add_run()
            r.text = t
            r.font.name = o.get("font", font)
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", bold)
            r.font.italic = o.get("italic", False)
            r.font.color.rgb = o.get("color", color)
    return tb


def bullets(slide, x, y, w, h, items, size=18, color=INK, gap=10):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(Inches(0.3)))
        pPr.set("indent", str(-Inches(0.3)))
        bu = etree.SubElement(pPr, qn("a:buChar"))
        bu.set("char", "•")
        runs = item if isinstance(item, list) else [(item, {})]
        for t, o in runs:
            r = p.add_run()
            r.text = t
            r.font.name = BODY
            r.font.size = Pt(o.get("size", size))
            r.font.bold = o.get("bold", False)
            r.font.color.rgb = o.get("color", color)
    return tb


def title(slide, t, color=INK):
    text(slide, 0.6, 0.4, 12.1, 0.9, t, 34, color, HEAD, True, name="Title")


def card(slide, x, y, w, h, fill=TINT, name=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.08
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    if name:
        s.name = name
    return s


def circle(slide, x, y, d, label, fill):
    s = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    tf = s.text_frame
    tf.margin_left = tf.margin_right = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = HEAD, Pt(20 if len(label) == 1 else 15), True, WHITE
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def footer(slide, n, dark=False):
    text(slide, 11.9, 6.95, 1.0, 0.4, f"{n} / 8", 11, WHITE if dark else MUTED, align=PP_ALIGN.RIGHT)


def bar_chart(slide, x, y, w, h, cats, values, colors, title_txt, log=False, fmt='0', axis_max=None, log_min=0.1):
    data = CategoryChartData()
    data.categories = cats
    data.add_series("Value", values)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), data)
    ch = gf.chart
    ch.has_legend = False
    ch.has_title = True
    ch.chart_title.text_frame.text = title_txt
    tp = ch.chart_title.text_frame.paragraphs[0]
    tp.runs[0].font.size, tp.runs[0].font.bold = Pt(14), True
    tp.runs[0].font.name, tp.runs[0].font.color.rgb = BODY, INK
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = fmt, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.name, dl.font.color.rgb = Pt(13), BODY, INK
    for i, c in enumerate(colors):
        pt = plot.series[0].points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = c
    va = ch.value_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)
    va.format.line.fill.background()
    va.tick_labels.font.size, va.tick_labels.font.color.rgb = Pt(11), MUTED
    ca = ch.category_axis
    ca.tick_labels.font.size, ca.tick_labels.font.color.rgb = Pt(12), INK
    ca.format.line.color.rgb = RGBColor(0xBB, 0xBB, 0xBB)
    if axis_max:
        va.maximum_scale = axis_max
    if log:
        scaling = va._element.find(qn("c:scaling"))
        lb = etree.SubElement(scaling, qn("c:logBase"))
        lb.set("val", "10")
        scaling.remove(lb)
        scaling.insert(0, lb)
        va.minimum_scale = log_min
        # make the category axis cross the value axis at its minimum,
        # so bars below 1 grow upwards from the bottom
        cat = ca._element
        for tag in ("c:crosses", "c:crossesAt"):
            for e in cat.findall(qn(tag)):
                cat.remove(e)
        ca_el = etree.Element(qn("c:crossesAt"))
        ca_el.set("val", str(log_min))
        cross_ax = cat.find(qn("c:crossAx"))
        cross_ax.addnext(ca_el)
    else:
        va.minimum_scale = 0
    return ch


# ------------------------------------------------------------------ data
S = json.loads(pathlib.Path(sys.argv[1]).read_text())
st = S["startup_s"]
mem = S["memory_mb"]
tp = S["throughput"]


def rps(alt, ep):
    return round(tp[f"{alt} | 10 VUs | {ep}"]["rps"][0])


# ------------------------------------------------------------------ 1 title
s = prs.slides.add_slide(BLANK)
bg(s, NAVY)
text(s, 0.9, 2.0, 11.5, 1.2, "Virtual Machines vs. Containers", 48, WHITE, HEAD, True)
text(s, 0.9, 3.15, 11.5, 0.8, "Same web API, same host, same limits — what really differs?", 24, RGBColor(0xCA, 0xDC, 0xFC))
text(s, 0.9, 4.6, 11.5, 1.4, [
    [("Soner Yanık", {"bold": True, "size": 20}), ("   B2305.010151", {"size": 18})],
    "SEN421 Cloud Architecture and Services — Topic 2, Part A",
    "Istanbul Aydın University · Fall 2026"], 16, WHITE)
circle(s, 11.0, 1.9, 0.75, "VM", VM)
circle(s, 11.9, 1.9, 0.75, "C", CONT)
notes(s, "Merhaba, ben Soner Yanık. Konum Topic 2: aynı web uygulamasını sanal makinede ve container'da "
         "çalıştırıp aradaki farkı ölçtüm.")

# ------------------------------------------------------------------ 2 question
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "The question")
bullets(s, 0.6, 1.5, 7.0, 2.2, [
    [("Every cloud workload needs isolation: ", {}), ("VM", {"bold": True, "color": VM}),
     (" (own kernel, hypervisor) or ", {}), ("container", {"bold": True, "color": CONT}), (" (shared kernel)", {})],
    "The choice decides how fast we scale, how densely we pack servers and what we pay",
], 20)
card(s, 0.6, 3.9, 7.0, 2.4)
text(s, 0.9, 4.05, 6.5, 0.5, "Research question", 18, CONT, HEAD, True)
text(s, 0.9, 4.55, 6.5, 1.7, [[
    ("For the same small web API with 2 vCPU and 2 GB, how do a container and a VM differ in ", {}),
    ("image size, startup time, memory", {"bold": True}), (" and ", {}), ("requests per second", {"bold": True}),
    (" — and why?", {})]], 18)
text(s, 8.4, 1.5, 4.3, 0.5, "My guess before measuring", 18, MUTED, BODY, True)
for i, (num, lab) in enumerate((("~10×", "faster"), ("~2×", "less memory"))):
    card(s, 8.4, 2.1 + i * 2.15, 4.3, 1.9)
    text(s, 8.4, 2.2 + i * 2.15, 4.3, 1.1, num, 60, CONT, HEAD, True, PP_ALIGN.CENTER)
    text(s, 8.4, 3.3 + i * 2.15, 4.3, 0.5, lab, 18, INK, align=PP_ALIGN.CENTER)
footer(s, 2)
notes(s, "Bulutta her iş yükünün izole edilmesi gerekiyor. İki yol var: kendi çekirdeği olan bir VM ya da çekirdeği "
         "paylaşan bir container. Bu seçim ne kadar hızlı ölçeklenebileceğimizi, bir sunucuya kaç servis "
         "sığdırabileceğimizi ve ne kadar ödeyeceğimizi belirliyor. Mühendislik sistemlerinde performansa ilgi "
         "duyduğum için bu farkı kendim ölçmek istedim. Ölçmeden önceki tahminim şuydu: container yaklaşık 10 kat "
         "hızlı olur ve 2 kat az bellek kullanır.")

# ------------------------------------------------------------------ 3 design
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Design")
pic = s.shapes.add_picture(str(ARCH), Inches(0.6), Inches(1.35), height=Inches(5.7))
pic.name = "Architecture diagram"
text(s, 0.6, 7.05, 6.5, 0.35, "Diagram drawn by the author in draw.io", 11, MUTED)
bullets(s, 7.5, 1.6, 5.3, 5.4, [
    [("Flask API", {"bold": True}), (" + gunicorn (2 workers): /hello, /compute, /health", {})],
    [("VM", {"bold": True, "color": VM}), (": VirtualBox 7.2, Ubuntu 22.04, kernel 5.15", {})],
    [("Container", {"bold": True, "color": CONT}), (": Docker 29.6, WSL2 kernel 6.18", {})],
    [("Control", {"bold": True}), (": container with the VM's exact Ubuntu, Python and OpenSSL", {})],
    [("Hyper-V sits under ", {}), ("both", {"bold": True})],
], 17, gap=12)
footer(s, 3)
notes(s, "Uygulama, gunicorn ile çalışan küçük bir Flask API'si. /hello hafif bir istek, /compute her istekte 20 bin "
         "SHA-256 hesaplıyor. Solda VirtualBox VM var: kendi Linux 5.15 çekirdeği, systemd ve cloud-init ile. Sağda "
         "Docker container var: WSL2'nin Linux 6.18 çekirdeğini paylaşıyor. İkisine de aynı kaynakları verdim: 2 CPU "
         "ve 2 GB RAM. Önemli bir detay: WSL2 açık olduğu için en altta Hyper-V çalışıyor. VirtualBox doğrudan VT-x "
         "kullanamıyor ve Hyper-V'nin API'si üzerinden (NEM modu) çalışıyor.")

# ------------------------------------------------------------------ 4 method
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Method")
items = [
    ("1", "Startup", "Start command → first HTTP 200 on /health, 5 successful cold starts"),
    ("2", "Memory", "docker stats vs. guest free + VirtualBox process on Windows"),
    ("3", "Load", "k6, 10 and 50 virtual users, 30 s, 3 runs per configuration"),
    ("4", "Pure CPU", "200k SHA-256 rounds without HTTP"),
]
for i, (n, head, desc) in enumerate(items):
    cx, cy = 0.6 + (i % 2) * 6.2, 1.6 + (i // 2) * 2.2
    card(s, cx, cy, 5.9, 1.9)
    circle(s, cx + 0.3, cy + 0.55, 0.8, n, CONT if i % 2 == 0 else VM)
    text(s, cx + 1.35, cy + 0.3, 4.4, 0.5, head, 20, INK, HEAD, True)
    text(s, cx + 1.35, cy + 0.85, 4.4, 0.95, desc, 16, INK)
text(s, 0.6, 6.15, 12.1, 0.5, [[("One script runs every measurement — only one alternative running at a time.   ", {}),
                                ("Laptop: i7-12700H, 16 GB, Windows 11 · cost: ", {"color": MUTED}),
                                ("0 USD", {"bold": True})]], 15)
footer(s, 4)
notes(s, "Bütün ölçümleri tek bir Python scripti yaptı, aynı anda yalnızca bir alternatif çalıştı. Açılış süresi: "
         "başlatma komutundan ilk HTTP 200 cevabına kadar geçen süre, 5 başarılı soğuk açılış. Bellek: container'da "
         "docker stats, VM'de hem misafir içi hem de Windows'taki VirtualBox süreci. Yük testi: k6 ile 10 ve 50 "
         "eşzamanlı kullanıcı, 30 saniye, her biri 3 tekrar. Her şey kendi bilgisayarımda çalıştı, yani maliyet 0 dolar.")

# ------------------------------------------------------------------ 5 startup + memory
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Results: startup and memory")
bar_chart(s, 0.5, 1.4, 6.1, 4.0, ["Container (slim)", "Container (jammy)", "VirtualBox VM"],
          [round(st["container"][0], 2), round(st["container-jammy"][0], 2), round(st["vm"][0], 1)],
          [CONT, CONT_L, VM], "Time to first HTTP 200 (s, log scale)", log=True, fmt='0.0#')
bar_chart(s, 6.8, 1.4, 6.1, 4.0, ["Container (cgroup)", "VM guest used", "VM app only", "VM process on host"],
          [mem["container | idle"]["used"][0], mem["vm | idle"]["used"][0], mem["vm | idle"]["app_rss_mb"][0],
           round(mem["vm | idle"]["host_private_mb"][0])],
          [CONT, VM, RGBColor(0xF0, 0xB2, 0x7A), VM_D], "Idle memory (MiB, log scale)", log=True, fmt='0',
          log_min=10)
text(s, 0.5, 5.6, 6.1, 1.2, [
    [("0.4–0.5 s", {"bold": True, "color": CONT}), (" vs. ", {}), ("30 s", {"bold": True, "color": VM}), ("  ⇒  ~60×", {})],
    [("8 of 13 VM boots hung", {"bold": True})]], 18, align=PP_ALIGN.CENTER)
text(s, 6.8, 5.6, 6.1, 1.2, [
    [("43 MiB", {"bold": True, "color": CONT}), (" vs. ", {}), ("234 MiB", {"bold": True, "color": VM}),
     (" in guest, ", {}), ("2.1 GiB", {"bold": True, "color": VM}), (" reserved", {})],
    [("Image: ", {}), ("202 MB", {"bold": True, "color": CONT}), (" vs. ", {}), ("2.7 GB", {"bold": True, "color": VM}),
     (" (~13×)", {})]], 18, align=PP_ALIGN.CENTER)
footer(s, 5)
notes(s, "Container yarım saniyenin altında açıldı, VM 30 saniyede. Yani yaklaşık 60 kat fark var. Daha da önemlisi: "
         "13 VM açılışının 8'i kilitlendi. Bellekte container 43 MB kullanıyor. VM'in içinde 234 MB kullanılıyor ve "
         "bunun yalnızca 76 MB'ı uygulama, gerisi misafir işletim sistemi. Windows tarafında ise VirtualBox, VM açılır "
         "açılmaz 2,1 GB ayırıyor. İmaj boyutu: 202 MB'a karşı 2,7 GB, yani 13 kat.")

# ------------------------------------------------------------------ 6 throughput
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Results: throughput — and a hypothesis that failed")
bar_chart(s, 0.5, 1.4, 3.6, 4.6, ["slim", "jammy", "VM"],
          [rps("container", "/hello"), rps("container-jammy", "/hello"), rps("vm", "/hello")],
          [CONT, CONT_L, VM], "GET /hello (req/s, 10 VUs)", axis_max=2400)
bar_chart(s, 4.2, 1.4, 3.6, 4.6, ["slim", "jammy", "VM"],
          [rps("container", "/compute"), rps("container-jammy", "/compute"), rps("vm", "/compute")],
          [CONT, CONT_L, VM], "GET /compute (req/s, 10 VUs)", axis_max=300)
bullets(s, 8.2, 1.5, 4.7, 5.3, [
    [("10 VUs: VM gives ", {}), ("50%", {"bold": True, "color": VM}), (" of container on /hello, ", {}),
     ("34–38%", {"bold": True, "color": VM}), (" on /compute", {})],
    [("50 VUs: ", {}), ("48% errors", {"bold": True, "color": VM}), (" on VM /hello → VirtualBox NAT, not the app", {})],
    "Hypothesis: older OpenSSL in VM causes the CPU gap",
    [("Control container with ", {}), ("same", {"bold": True}), (" OpenSSL: still fast (237 req/s)", {})],
    [("⇒ gap comes from the ", {}), ("virtualization layer", {"bold": True})],
], 17, gap=12)
footer(s, 6)
notes(s, "10 kullanıcıda VM, container'ın /hello'da yarısı kadar, /compute'ta üçte biri kadar istek karşılıyor. 50 "
         "kullanıcıda VM'de isteklerin yaklaşık yarısı hata verdi. Ama aynı VM 10 kullanıcıda hatasızdı, yani sorun "
         "uygulamada değil, VirtualBox'ın NAT ağ katmanında. İşlemci farkı literatürden büyük çıkınca bir hipotez "
         "kurdum: VM'deki OpenSSL eski (3.0.2), container'daki yeni (3.5.7). Bunu test etmek için VM ile birebir aynı "
         "Ubuntu, Python ve OpenSSL sürümlerine sahip bir kontrol container'ı yaptım. O da hızlı çıktı, 237 istek/s. "
         "Yani hipotezim yanlıştı ve fark sanallaştırma katmanından geliyor.")

# ------------------------------------------------------------------ 7 cost + security
s = prs.slides.add_slide(BLANK)
bg(s, WHITE)
title(s, "Cost and security")
text(s, 0.6, 1.45, 6.1, 0.8, ["Cost: 8 isolated services per month", "Azure list prices, accessed 22 Nov 2026"], 15, MUTED)
for i, (amt, lab, col) in enumerate((("$280", "8 × B2s VM", VM), ("$168", "1 × D4s_v5 + 8 containers", CONT))):
    card(s, 0.6 + i * 3.1, 2.4, 2.9, 2.3)
    text(s, 0.6 + i * 3.1, 2.55, 2.9, 1.1, amt, 54, col, HEAD, True, PP_ALIGN.CENTER)
    text(s, 0.6 + i * 3.1, 3.75, 2.9, 0.8, lab, 15, INK, align=PP_ALIGN.CENTER)
text(s, 0.6, 5.0, 6.0, 1.3, [[("⇒ ~40% cheaper", {"bold": True, "size": 24})],
                             [("Experiments: ", {}), ("0 USD", {"bold": True})]], 18)
card(s, 7.0, 1.45, 5.8, 4.3)
text(s, 7.3, 1.6, 5.3, 0.5, "Security and shared responsibility", 18, INK, HEAD, True)
bullets(s, 7.3, 2.2, 5.3, 4.3, [
    [("VM", {"bold": True, "color": VM}), (": separate kernel = stronger boundary", {})],
    [("Container", {"bold": True, "color": CONT}), (": one shared kernel for all tenants", {})],
    "Cloud: provider → hardware, hypervisor (+ host kernel if managed); me → image, patches, secrets, ports",
    "To fix before production: run container as non-root, publish port on 127.0.0.1 only",
], 16, gap=10)
footer(s, 7)
notes(s, "Maliyet modeli: Azure'da 8 izole servis. Her servise bir B2s VM verirsek ayda 280 dolar tutuyor. Hepsini "
         "container olarak tek bir D4s_v5 makinesine koyarsak 168 dolar. Bu da yaklaşık yüzde 40 tasarruf. Fiyatlar "
         "Azure'un resmi fiyat API'sinden, 22 Kasım tarihli. Güvenlik tarafında ise VM daha güçlü: ayrı bir çekirdek "
         "var. Container'larda tüm kiracılar tek bir çekirdeği paylaşıyor. Bulutta donanım ve hypervisor sağlayıcının "
         "sorumluluğunda. İmaj, yamalar, gizli bilgiler ve portlar benim sorumluluğumda. Kendi kurulumumda iki eksik "
         "gördüm: container root olarak çalışıyordu ve port tüm ağ arayüzlerine açıktı.")

# ------------------------------------------------------------------ 8 lessons
s = prs.slides.add_slide(BLANK)
bg(s, NAVY)
title(s, "Lessons and recommendation", WHITE)
rows = [("Startup", "10×", "60×"), ("Memory", "2×", "5–50×"), ("Throughput", "10×", "2–3×")]
text(s, 0.6, 1.5, 5.6, 0.5, [[("Guess", {"color": RGBColor(0xCA, 0xDC, 0xFC)}), ("  vs.  ", {}),
                               ("measured", {"bold": True})]], 18, WHITE)
for i, (k, g, m) in enumerate(rows):
    y = 2.15 + i * 1.25
    card(s, 0.6, y, 5.6, 1.05, RGBColor(0x2A, 0x36, 0x50))
    text(s, 0.85, y + 0.25, 2.2, 0.6, k, 18, WHITE, BODY, True)
    text(s, 3.0, y + 0.2, 1.3, 0.7, g, 22, RGBColor(0xCA, 0xDC, 0xFC), align=PP_ALIGN.CENTER)
    text(s, 4.3, y + 0.12, 1.8, 0.8, m, 28, VM, HEAD, True, PP_ALIGN.CENTER)
bullets(s, 6.8, 1.6, 6.0, 4.8, [
    [("Containers", {"bold": True, "color": CONT_L}), (" for many small, stateless services that must scale fast", {})],
    [("VMs", {"bold": True, "color": VM}), (" when strong kernel isolation or another OS is needed", {})],
    [("Biggest surprise: the ", {}), ("nested Hyper-V + VirtualBox", {"bold": True}),
     (" setup, not virtualization itself, caused the worst penalties", {})],
    "Always test a hypothesis with a control experiment",
    "Next: repeat on Linux/KVM and in a cloud autoscaling group",
], 17, WHITE, gap=12)
text(s, 0.6, 6.55, 12.1, 0.5, "Code and data: github.com/soneryanik/cloud-vm-container-test  and  SEN421_B2305.010151_Topic2_code.zip", 14,
     RGBColor(0xCA, 0xDC, 0xFC), align=PP_ALIGN.CENTER)
footer(s, 8, dark=True)
notes(s, "Tahminim ile gerçek sonuç: açılışta fark 10 değil 60 kat çıktı, bellekte 2 değil 5 ile 50 kat arası, "
         "throughput'ta ise 10 değil 2–3 kat. Önerim şu: çok sayıda küçük ve hızlı ölçeklenmesi gereken servis için "
         "container, güçlü izolasyon veya farklı bir işletim sistemi gerekiyorsa VM. En büyük ders: en kötü sonuçlara "
         "sanallaştırmanın kendisi değil, iç içe Hyper-V + VirtualBox kurulumu yol açtı. Teşekkürler.")

prs.save(sys.argv[2])
print("written", sys.argv[2])
