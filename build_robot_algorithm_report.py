import html
import os
import textwrap
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties


OUT_DIR = Path("report_output")
OUT_DIR.mkdir(exist_ok=True)

DOCX_PATH = OUT_DIR / "robot_algorithm_ga_report.docx"
PDF_PATH = OUT_DIR / "robot_algorithm_ga_report.pdf"
FLOW_PNG = OUT_DIR / "figure_robot_algorithm_flow.png"
BAR_PNG = OUT_DIR / "figure_ga_applicability.png"

FONT_PATH = r"C:\Windows\Fonts\meiryo.ttc"
FONT = FontProperties(fname=FONT_PATH)
FONT_BOLD = FontProperties(fname=r"C:\Windows\Fonts\meiryob.ttc")


def make_figures():
    plt.rcParams["font.family"] = FONT.get_name()

    fig, ax = plt.subplots(figsize=(9, 3.2), dpi=180)
    ax.axis("off")
    boxes = [
        ("環境認識", "カメラ・LiDAR・GPS・IMU\n物体認識 / 位置推定 / センサ融合"),
        ("状況判断", "線形識別・機械学習・深層学習\n行動選択 / 危険判断 / 状態推定"),
        ("行動生成", "経路計画・動的計画法・制御\n移動 / 操作 / 障害物回避"),
    ]
    xs = [0.15, 0.50, 0.85]
    for i, (title, body) in enumerate(boxes):
        ax.text(
            xs[i], 0.58, title + "\n" + body,
            ha="center", va="center", fontproperties=FONT,
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.55", fc="#EAF2F8", ec="#2E74B5", lw=1.4),
        )
        if i < len(boxes) - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.16, 0.58), xytext=(xs[i] + 0.16, 0.58),
                        arrowprops=dict(arrowstyle="->", lw=1.8, color="#2E74B5"))
    ax.text(0.5, 0.13, "図1　自律ロボットにおける情報処理の基本的な流れ（Thrun et al., 2005; LaValle, 2006を基に作成）",
            ha="center", va="center", fontproperties=FONT_BOLD, fontsize=10)
    fig.tight_layout()
    fig.savefig(FLOW_PNG, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=180)
    dominated_x = [2.0, 2.8, 3.5, 4.2, 4.8, 5.4, 6.0, 6.8, 7.5, 8.1]
    dominated_y = [8.2, 7.8, 7.2, 6.6, 6.0, 5.4, 4.9, 4.5, 4.1, 3.8]
    pareto_x = [1.4, 2.0, 2.8, 3.8, 5.2, 6.8, 8.6]
    pareto_y = [9.2, 8.4, 7.5, 6.4, 5.0, 3.7, 2.6]
    ax.scatter(dominated_x, dominated_y, s=80, color="#A9B7C6", label="支配される解")
    ax.plot(pareto_x, pareto_y, color="#2E74B5", lw=2.0, label="パレートフロント")
    ax.scatter(pareto_x, pareto_y, s=95, color="#F39C12", edgecolor="#7A5A00", zorder=3, label="非劣解")
    ax.annotate("速度を重視", xy=(8.6, 2.6), xytext=(7.2, 1.7),
                arrowprops=dict(arrowstyle="->", color="#555555"), fontproperties=FONT, fontsize=9)
    ax.annotate("省エネルギーを重視", xy=(1.4, 9.2), xytext=(2.0, 9.6),
                arrowprops=dict(arrowstyle="->", color="#555555"), fontproperties=FONT, fontsize=9)
    ax.set_xlabel("移動時間（短いほど良い）", fontproperties=FONT)
    ax.set_ylabel("消費電力（低いほど良い）", fontproperties=FONT)
    ax.set_title("多目的GAにおけるパレート最適解の概念", fontproperties=FONT_BOLD, fontsize=13)
    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.grid(alpha=0.25)
    ax.legend(prop=FONT, loc="lower left")
    for tick in ax.get_xticklabels() + ax.get_yticklabels():
        tick.set_fontproperties(FONT)
    fig.text(0.5, 0.01, "図2　多目的遺伝的アルゴリズムのパレート最適概念（Deb et al., 2002を基に作成）",
             ha="center", fontproperties=FONT_BOLD, fontsize=10)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(BAR_PNG, bbox_inches="tight")
    plt.close(fig)


REPORT = [
    ("title", "ロボットにおけるアルゴリズムと遺伝的アルゴリズムに関する考察"),
    ("meta", "提出用レポート"),
    ("h1", "1. はじめに"),
    ("p", "ロボットが自律的に動作するためには、周囲の環境を認識し、状況を判断し、その判断に基づいて適切な行動を生成する必要がある。これらの処理は単独で完結するものではなく、センサ情報の取得、情報の解釈、移動や操作の実行が連続的につながることでロボットの知能的な振る舞いが実現される。"),
    ("p", "本レポートでは、ロボットで利用される代表的なアルゴリズムを「環境認識」「状況判断」「行動生成」の三つの観点から整理する。また、最適化手法として広く用いられる遺伝的アルゴリズム（Genetic Algorithm: GA）と、その派生・関連研究である分散遺伝的アルゴリズム、対話型遺伝的アルゴリズム、多目的遺伝的アルゴリズム、遺伝的プログラミングについて考察し、ロボット分野への応用可能性を検討する。"),
    ("image", str(FLOW_PNG)),
    ("h1", "2. ロボットにおけるアルゴリズムの分類"),
    ("h2", "2.1 環境認識に関するアルゴリズム"),
    ("p", "環境認識は、ロボットが外界の状態を把握するための処理である。代表的な例としてロボットビジョンがあり、カメラ画像から物体の種類、位置、姿勢を推定する。近年では深層学習を用いた物体検出や画像セグメンテーションが普及し、人や障害物、作業対象を高精度に識別できるようになっている。"),
    ("p", "また、LiDAR、超音波センサ、GPS、加速度センサ、ジャイロセンサなども重要である。単一のセンサには誤差や死角があるため、複数のセンサ情報を統合するセンサ融合が用いられる。たとえば移動ロボットでは、LiDARによる距離情報とIMUによる姿勢情報を組み合わせることで、自己位置推定や地図作成の精度を高めることができる。"),
    ("h2", "2.2 状況判断に関するアルゴリズム"),
    ("p", "状況判断は、認識した情報を基にロボットがどのような行動を取るべきかを決定する処理である。基本的な手法としては線形識別機や決定木などの分類アルゴリズムがあり、センサ値や画像特徴量から状況を分類する。たとえば、障害物が近いか、対象物を把持できる位置にあるか、進行してよい状態かを判断する。"),
    ("p", "近年では機械学習や深層学習により、複雑な環境における判断能力が向上している。自動運転車では、歩行者、信号機、車線、他車両の位置を認識したうえで、停止、減速、進行、回避などを判断する必要がある。この段階では、単に正確に分類するだけでなく、安全性、リアルタイム性、説明可能性も重要な評価軸となる。"),
    ("h2", "2.3 行動生成に関するアルゴリズム"),
    ("p", "行動生成は、判断結果を実際の動作に変換する処理である。代表的な手法には経路計画、軌道生成、動作解析、制御アルゴリズムがある。経路計画では、目的地までの安全で効率的な移動経路を求める。A*探索やダイクストラ法は地図上の最短経路探索に使われ、RRTなどのサンプリングベース手法は高次元の動作計画に用いられる。"),
    ("p", "動的計画法は、複雑な問題を部分問題に分割し、最適な解を効率的に求める手法である。ロボットの移動やエネルギー管理、作業順序の最適化などに応用できる。ただし、状態数が増えると計算量が大きくなるため、近似手法や学習手法と組み合わせることが重要になる。"),
    ("table", "表1　ロボットにおけるアルゴリズムの分類", [
        ["分類", "代表的なアルゴリズム", "主な役割", "応用例"],
        ["環境認識", "画像処理、物体認識、SLAM、センサ融合", "外界や自己位置を把握する", "障害物検出、地図作成、対象物認識"],
        ["状況判断", "線形識別、機械学習、深層学習、ルールベース推論", "認識結果から行動方針を決める", "自動運転の停止判断、作業可否判定"],
        ["行動生成", "A*、RRT、動的計画法、PID制御、モデル予測制御", "移動や操作の具体的な動作を生成する", "経路計画、アーム制御、障害物回避"],
    ]),
    ("h1", "3. 遺伝的アルゴリズム（GA）の概要"),
    ("p", "遺伝的アルゴリズムは、生物の進化における選択、交叉、突然変異の考え方を模倣した探索・最適化手法である。まず複数の候補解を個体群として生成し、各個体の良さを適応度として評価する。その後、適応度の高い個体を選択し、交叉によって特徴を組み合わせ、突然変異によって新しい候補を生み出す。この処理を繰り返すことで、より良い解を探索する。"),
    ("p", "GAの特徴は、解空間が広く、数式的に最適解を求めにくい問題にも適用しやすい点である。ロボット分野では、経路計画、制御パラメータ調整、ロボット形状設計、群ロボットの役割分担、センサ配置最適化などに応用できる。一方で、計算回数が多くなりやすく、適応度関数の設計によって結果が大きく変わるという課題もある。"),
    ("h1", "4. GAの派生・関連研究"),
    ("h2", "4.1 分散遺伝的アルゴリズム（DGA）"),
    ("p", "分散遺伝的アルゴリズムは、個体群を複数の島やグループに分け、それぞれで進化計算を行う手法である。一定の間隔で個体を移住させることで、多様性を保ちながら探索を進める。ロボットの経路計画では、複数候補を並列に探索できるため、局所最適解に陥りにくい。"),
    ("h2", "4.2 対話型遺伝的アルゴリズム（iGA）"),
    ("p", "対話型遺伝的アルゴリズムは、人間の主観的評価を適応度として利用する手法である。数値化しにくい好みや感覚を最適化に取り込めるため、ロボットの動作デザイン、コミュニケーション動作、表情やジェスチャ生成などに向いている。ただし、人間が評価を繰り返す負担が大きいため、評価回数を減らす工夫が必要である。"),
    ("h2", "4.3 多目的遺伝的アルゴリズム（MOGA）"),
    ("p", "多目的遺伝的アルゴリズムは、複数の評価基準を同時に扱う手法である。ロボットでは、速度、消費電力、安全性、安定性、経路長など複数の要求が衝突することが多い。MOGAを用いることで、単一の最適解ではなく、目的間のバランスが異なる複数の有力解を得ることができる。"),
    ("h2", "4.4 遺伝的プログラミング（GP）"),
    ("p", "遺伝的プログラミングは、数値パラメータだけでなく、プログラム構造そのものを進化させる手法である。ロボットの制御ルールや行動方針を自動生成できる可能性があり、未知環境での適応行動の研究に有効である。ただし、生成されたプログラムの安全性や解釈性を確認する仕組みが不可欠である。"),
    ("image", str(BAR_PNG)),
    ("p", "図2は、DebらによるNSGA-IIの研究で扱われる非劣ソートとパレート最適の考え方を、ロボットの移動時間と消費電力のトレードオフに置き換えて模式的に示したものである。点の座標は実測データではなく、パレートフロントの意味を説明するための概念図である。"),
    ("h1", "5. 応用の可能性に関する考察"),
    ("p", "ロボットにおけるアルゴリズムの応用可能性は、単に個別技術を導入するだけでなく、認識、判断、行動生成を一体として設計する点にある。たとえば災害対応ロボットでは、環境認識によって瓦礫や人の位置を把握し、状況判断によって危険度や救助優先度を決め、行動生成によって安全な移動経路を計画する必要がある。"),
    ("p", "GAはこのような複雑な設計問題に対して、複数条件を満たす候補を探索する手段として有効である。特に、ロボットの移動経路、消費電力、作業時間、安全距離などは互いにトレードオフの関係にあるため、MOGAのような多目的最適化の重要性は高い。また、人間と協働するサービスロボットでは、iGAによって人間が自然だと感じる動作を探索する応用が考えられる。"),
    ("p", "今後は、GAを単独で使うだけでなく、深層学習、強化学習、シミュレーション、デジタルツインと組み合わせることで、より実用的なロボット設計が可能になると考えられる。ただし、探索結果をそのまま実機に適用すると安全性の問題が生じる可能性があるため、シミュレーション検証、制約条件の明確化、フェイルセーフ設計が必要である。"),
    ("table", "表2　GA関連手法のロボット応用可能性", [
        ["手法", "強み", "ロボットへの応用可能性", "課題"],
        ["GA", "広い解空間を探索できる", "経路計画、パラメータ調整、設計最適化", "計算量、適応度関数設計"],
        ["DGA", "多様性を維持しやすい", "複数経路候補の並列探索、群ロボット", "移住周期や分割方法の設計"],
        ["iGA", "人間の感性を反映できる", "動作デザイン、対話動作、外観評価", "評価者の負担、主観のばらつき"],
        ["MOGA", "複数目的を同時に扱える", "速度・安全性・電力の同時最適化", "解の選択基準が必要"],
        ["GP", "行動ルールを自動生成できる", "制御プログラム、適応行動の生成", "安全性、解釈性、検証コスト"],
    ]),
    ("h1", "6. まとめ"),
    ("p", "ロボットにおけるアルゴリズムは、環境認識、状況判断、行動生成の三段階に大別できる。環境認識ではセンサや画像処理によって外界を把握し、状況判断では識別手法やAIによって意思決定を行い、行動生成では経路計画や制御アルゴリズムによって実際の動作を実現する。"),
    ("p", "遺伝的アルゴリズムは、これらの各段階を支援する最適化技術として有効であり、DGA、iGA、MOGA、GPなどの派生手法によって応用範囲が広がっている。特に、複雑な制約や複数の評価基準を持つロボットシステムでは、GA関連手法が有力な選択肢となる。今後のロボット技術では、GAを他のAI技術と組み合わせ、安全性と実用性を両立させる設計が重要になると考えられる。"),
    ("h1", "参考文献"),
    ("p", "・S. Thrun, W. Burgard, and D. Fox, Probabilistic Robotics, MIT Press, 2005."),
    ("p", "・S. M. LaValle, Planning Algorithms, Cambridge University Press, 2006."),
    ("p", "・J. H. Holland, Adaptation in Natural and Artificial Systems, University of Michigan Press, 1975."),
    ("p", "・D. E. Goldberg, Genetic Algorithms in Search, Optimization, and Machine Learning, Addison-Wesley, 1989."),
    ("p", "・K. Deb, A. Pratap, S. Agarwal, and T. Meyarivan, “A Fast and Elitist Multiobjective Genetic Algorithm: NSGA-II,” IEEE Transactions on Evolutionary Computation, 6(2), pp. 182-197, 2002."),
    ("p", "・J. R. Koza, Genetic Programming: On the Programming of Computers by Means of Natural Selection, MIT Press, 1992."),
    ("p", "・S. Russell and P. Norvig, Artificial Intelligence: A Modern Approach, Pearson."),
]


def esc(s):
    return html.escape(str(s), quote=True)


def paragraph_xml(text, style=None, bold=False, size=22, color="000000", spacing_after=120):
    pstyle = f'<w:pStyle w:val="{style}"/>' if style else ""
    b = "<w:b/>" if bold else ""
    return (
        f'<w:p><w:pPr>{pstyle}<w:spacing w:after="{spacing_after}" w:line="280" w:lineRule="auto"/></w:pPr>'
        f'<w:r><w:rPr><w:rFonts w:ascii="Meiryo" w:eastAsia="Meiryo"/>{b}<w:sz w:val="{size}"/><w:color w:val="{color}"/></w:rPr>'
        f'<w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>'
    )


def image_xml(rid, cx=5486400, cy=2500000):
    return f'''<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="160"/></w:pPr><w:r><w:drawing>
<wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/>
<wp:docPr id="{rid + 10}" name="Figure {rid}"/><wp:cNvGraphicFramePr/>
<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:nvPicPr><pic:cNvPr id="{rid + 20}" name="figure.png"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="rId{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''


def table_xml(rows):
    widths = [1800, 2700, 2700, 2160] if len(rows[0]) == 4 else [1500, 2300, 3000, 2560]
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths[:len(rows[0])])
    trs = []
    for i, row in enumerate(rows):
        cells = []
        for j, cell in enumerate(row):
            fill = '<w:shd w:fill="F2F4F7"/>' if i == 0 else ""
            bold = "<w:b/>" if i == 0 else ""
            cells.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{widths[j]}" w:type="dxa"/>{fill}'
                f'<w:tcMar><w:top w:w="80" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:start w:w="120" w:type="dxa"/><w:end w:w="120" w:type="dxa"/></w:tcMar></w:tcPr>'
                f'<w:p><w:pPr><w:spacing w:after="40" w:line="260" w:lineRule="auto"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Meiryo" w:eastAsia="Meiryo"/>{bold}<w:sz w:val="18"/></w:rPr><w:t>{esc(cell)}</w:t></w:r></w:p></w:tc>'
            )
        trs.append("<w:tr>" + "".join(cells) + "</w:tr>")
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:tblInd w:w="120" w:type="dxa"/>'
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="D9E2EC"/><w:left w:val="single" w:sz="4" w:color="D9E2EC"/><w:bottom w:val="single" w:sz="4" w:color="D9E2EC"/><w:right w:val="single" w:sz="4" w:color="D9E2EC"/><w:insideH w:val="single" w:sz="4" w:color="D9E2EC"/><w:insideV w:val="single" w:sz="4" w:color="D9E2EC"/></w:tblBorders></w:tblPr>'
        f'<w:tblGrid>{grid}</w:tblGrid>' + "".join(trs) + "</w:tbl>"
    )


def build_docx():
    image_rels = []
    body = []
    image_id = 1
    for kind, *payload in REPORT:
        if kind == "title":
            body.append(paragraph_xml(payload[0], None, bold=True, size=32, color="0B2545", spacing_after=80))
        elif kind == "meta":
            body.append(paragraph_xml(payload[0], None, size=20, color="555555", spacing_after=260))
        elif kind == "h1":
            body.append(paragraph_xml(payload[0], "Heading1", bold=True, size=28, color="2E74B5", spacing_after=120))
        elif kind == "h2":
            body.append(paragraph_xml(payload[0], "Heading2", bold=True, size=24, color="2E74B5", spacing_after=80))
        elif kind == "p":
            body.append(paragraph_xml(payload[0], None, size=21, spacing_after=120))
        elif kind == "image":
            body.append(image_xml(image_id))
            image_rels.append((image_id, Path(payload[0])))
            image_id += 1
        elif kind == "table":
            caption, rows = payload
            body.append(paragraph_xml(caption, None, bold=True, size=19, color="1F4D78", spacing_after=80))
            body.append(table_xml(rows))
            body.append(paragraph_xml("", None, size=8, spacing_after=120))

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
<w:body>{''.join(body)}
<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>
</w:body></w:document>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Meiryo" w:eastAsia="Meiryo"/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="320" w:after="160"/></w:pPr><w:rPr><w:b/><w:color w:val="2E74B5"/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:color w:val="2E74B5"/><w:sz w:val="26"/></w:rPr></w:style>
</w:styles>'''

    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>']
    for rid, path in image_rels:
        rels.append(f'<Relationship Id="rId{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{path.name}"/>')
    document_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + '</Relationships>'
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>'''
    app_xml = '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Codex</Application></Properties>'
    core_xml = '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>ロボットにおけるアルゴリズムと遺伝的アルゴリズムに関する考察</dc:title></cp:coreProperties>'

    with zipfile.ZipFile(DOCX_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("docProps/app.xml", app_xml)
        z.writestr("docProps/core.xml", core_xml)
        z.writestr("word/document.xml", document_xml)
        z.writestr("word/styles.xml", styles_xml)
        z.writestr("word/_rels/document.xml.rels", document_rels)
        for _, path in image_rels:
            z.write(path, f"word/media/{path.name}")


def draw_wrapped_page(pdf, lines, title=None):
    fig = plt.figure(figsize=(8.27, 11.69), dpi=150)
    fig.patch.set_facecolor("white")
    y = 0.94
    if title:
        fig.text(0.08, y, title, fontproperties=FONT_BOLD, fontsize=15, color="#0B2545")
        y -= 0.045
    for kind, text in lines:
        if kind == "h1":
            y -= 0.012
            fig.text(0.08, y, text, fontproperties=FONT_BOLD, fontsize=13, color="#2E74B5")
            y -= 0.034
        elif kind == "h2":
            fig.text(0.08, y, text, fontproperties=FONT_BOLD, fontsize=11.5, color="#2E74B5")
            y -= 0.030
        elif kind == "p":
            wrapped = textwrap.wrap(text, width=55)
            for line in wrapped:
                fig.text(0.08, y, line, fontproperties=FONT, fontsize=9.4, color="#111111")
                y -= 0.021
            y -= 0.010
        if y < 0.08:
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            fig = plt.figure(figsize=(8.27, 11.69), dpi=150)
            fig.patch.set_facecolor("white")
            y = 0.94
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def build_pdf():
    with PdfPages(PDF_PATH) as pdf:
        page_lines = []
        for item in REPORT:
            kind = item[0]
            if kind in ("title", "meta"):
                continue
            if kind == "image":
                draw_wrapped_page(pdf, page_lines, title="ロボットにおけるアルゴリズムとGA")
                page_lines = []
                fig = plt.figure(figsize=(8.27, 11.69), dpi=150)
                img = plt.imread(item[1])
                ax = fig.add_axes([0.08, 0.25, 0.84, 0.48])
                ax.imshow(img)
                ax.axis("off")
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
            elif kind == "table":
                caption, rows = item[1], item[2]
                draw_wrapped_page(pdf, page_lines, title="ロボットにおけるアルゴリズムとGA")
                page_lines = []
                fig, ax = plt.subplots(figsize=(8.27, 11.69), dpi=150)
                ax.axis("off")
                ax.text(0.02, 0.95, caption, fontproperties=FONT_BOLD, fontsize=11, color="#1F4D78")
                tbl = ax.table(cellText=rows[1:], colLabels=rows[0], cellLoc="left", loc="center")
                tbl.auto_set_font_size(False)
                tbl.set_fontsize(7.2)
                tbl.scale(1, 2.05)
                for _, cell in tbl.get_celld().items():
                    cell.get_text().set_fontproperties(FONT)
                    cell.set_edgecolor("#D9E2EC")
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
            else:
                page_lines.append((kind, item[1]))
        if page_lines:
            draw_wrapped_page(pdf, page_lines, title="ロボットにおけるアルゴリズムとGA")


def main():
    make_figures()
    build_docx()
    build_pdf()
    print(DOCX_PATH)
    print(PDF_PATH)


if __name__ == "__main__":
    main()
