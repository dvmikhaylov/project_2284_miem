import pandas as pd
import streamlit as st
import plotly.graph_objects as go

import api_client
from streamlit_app.ui_guard import require_api

st.set_page_config(page_title="Дашборд", layout="wide")
st.title("Карта бизнес-процессов")

require_api()

procs = api_client.list_processes()
if not procs:
    st.warning("Каталог процессов пуст — перезапустите API (инициализация БД).")
    st.stop()
categories = sorted({p["category"] for p in procs})
cat_options = ["Все категории"] + categories

cat_sel = st.selectbox("Категория (для матрицы и топа ниже)", options=cat_options, key="dash_category_filter")
cat_param = None if cat_sel == "Все категории" else cat_sel

pg_options = {
    "catalog": "Каталог (как в справочнике)",
    "macro": "Процессы: крупные группы (MACRO)",
    "meso": "Процессы: подтипы (MESO)",
    "free": "Процессы: как в тексте (свободная формулировка)",
}
ag_options = {
    "original": "Акторы: как в связях (оригинал)",
    "meso": "Акторы: подкатегории (actor_subcategory)",
    "macro": "Акторы: группы (actor_category)",
}
c0, c0b = st.columns(2)
with c0:
    proc_group = st.selectbox(
        "Группировка процессов на графиках",
        options=list(pg_options.keys()),
        format_func=lambda k: pg_options[k],
        key="dash_process_group",
    )
with c0b:
    actor_group = st.selectbox(
        "Группировка акторов",
        options=list(ag_options.keys()),
        format_func=lambda k: ag_options[k],
        key="dash_actor_group",
    )
if proc_group != "catalog":
    st.caption("Фильтр «Категория» выше учитывается только в режиме **Каталог**.")

c1, c2 = st.columns(2)
with c1:
    tn_act = st.slider("Топ акторов (матрица)", 8, 40, 22, key="dash_tn_act")
with c2:
    tn_proc = st.slider("Топ подпроцессов в столбцах", 6, 35, 18, key="dash_tn_proc")

st.subheader("Граф подпроцессов")
bubbles = api_client.process_bubbles(process_group=proc_group).get("items") or []
if not bubbles:
    st.info("Нет обработанных документов с привязкой к процессам.")
else:
    # Сортировка по убыванию веса: сверху сильнее сигнал; одна строка — один процесс (без наложения).
    ranked = sorted(bubbles, key=lambda b: float(b.get("weight_norm", 0)), reverse=True)
    names_full = [str(b.get("process_name", "")) for b in ranked]
    weights = [float(b["weight_norm"]) for b in ranked]

    def _short_label(s: str, max_len: int = 52) -> str:
        s = s.strip() or "—"
        return s if len(s) <= max_len else s[: max_len - 1] + "…"

    y_labels = [f"{i + 1}. {_short_label(n)}" for i, n in enumerate(names_full)]
    marker_sizes = [max(14.0, 16.0 + 70.0 * w) for w in weights]
    wmax = max(weights) if weights else 1.0

    fig = go.Figure(
        data=go.Scatter(
            x=weights,
            y=y_labels,
            mode="markers",
            marker=dict(
                size=marker_sizes,
                sizemode="diameter",
                sizemin=10,
                opacity=0.72,
                line=dict(width=1, color="rgba(255,255,255,0.25)"),
                color="rgba(99, 160, 255, 0.85)",
            ),
            hovertext=names_full,
            hovertemplate="<b>%{hovertext}</b><br>Норм. вес: %{x:.3f}<extra></extra>",
        )
    )
    row_h = 30
    fig.update_layout(
        height=int(min(2000, max(420, 100 + row_h * len(ranked)))),
        xaxis=dict(
            title="Нормированный вес",
            range=[0, max(0.08, wmax * 1.18)],
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            title="",
            automargin=True,
            categoryorder="array",
            # В Plotly первая категория в списке — снизу; разворачиваем, чтобы №1 (сильнее всех) был сверху.
            categoryarray=list(reversed(y_labels)),
        ),
        margin=dict(l=16, r=32, t=40, b=56),
        hoverlabel=dict(align="left"),
    )
    st.plotly_chart(fig, width="stretch", key="dash_bubbles")
    st.caption(
        "Каждая строка — отдельный процесс (сверху сильнее сигнал). Размер маркера — тот же нормированный вес. "
        "Полное название — при наведении. Ниже — **матрица актор — подпроцесс**."
    )

st.divider()

st.subheader("Матрица: актор — подпроцесс")
st.caption(
    "По умолчанию учитываются **все категории**: в столбцах — топ подпроцессов по силе сигнала. "
    "Выберите **одну категорию** выше — в столбцах останутся только её подпроцессы. "
    "Значения строятся по документам «успех» с извлечёнными **связями** (вклад актора = source связи)."
)

hm = api_client.heatmap_actor_process(
    category=cat_param if proc_group == "catalog" else None,
    top_n_actors=tn_act,
    top_n_processes=tn_proc,
    process_group=proc_group,
    actor_group=actor_group,
)
actors = hm.get("actors") or []
sub_labels = hm.get("subprocess_labels") or []
matrix = hm.get("matrix") or []
col_ids = hm.get("column_process_ids") or []

if not matrix:
    st.info("Нет данных: загрузите документы с совпадениями по процессам и извлечёнными связями.")
else:
    max_actor_len = max((len(str(a)) for a in actors), default=0)
    left_margin = int(min(520, 48 + max_actor_len * 5.8))
    fig2 = go.Figure(data=go.Heatmap(z=matrix, x=sub_labels, y=actors, colorscale="Blues"))
    fig2.update_layout(
        height=max(520, 20 * len(actors) + 160),
        xaxis_title="Процесс (столбец)",
        yaxis_title="Актор",
        margin=dict(l=left_margin, r=80, t=48, b=160),
        yaxis=dict(automargin=True, side="left"),
        xaxis=dict(automargin=True),
    )
    fig2.update_xaxes(tickangle=-40)
    st.plotly_chart(fig2, width="stretch", key="heatmap_actor_subproc")

if col_ids and cat_param is None and proc_group == "catalog":
    st.caption(
        "Чтобы сузить выбор по категории: укажите её в списке **Категория** — в столбцах останутся только подпроцессы этой группы."
    )

st.subheader("Топ пар: актор — подпроцесс")
st.caption(
    "Тот же фильтр категории, что у матрицы. **Документов** — сколько файлов дают вклад в строку. "
    "Ниже выберите пару — покажем **SHA-256** и вклад каждого файла (раздел «Документ по хэшу»)."
)
rows = (
    api_client.top_actor_process(
        category=cat_param if proc_group == "catalog" else None,
        limit=45,
        process_group=proc_group,
        actor_group=actor_group,
    ).get("items")
    or []
)
if not rows:
    st.caption("Пусто при отсутствии связей и совпадений с процессами.")
else:
    tbl = pd.DataFrame(
        [
            {
                "Актор": r["actor"],
                "Категория": r["category"],
                "Подпроцесс": r["subprocess"],
                "Ключ процесса": r.get("process_key", ""),
                "ID каталога": r["process_id"],
                "Документов": r["documents_count"],
                "Вес": r["weight"],
                "Вес (норм.)": r["weight_norm"],
            }
            for r in rows
        ]
    )
    st.dataframe(tbl, width="stretch", hide_index=True)

    ix = st.selectbox(
        "Детализация: выберите пару",
        range(len(rows)),
        format_func=lambda i: (
            f"{str(rows[i].get('subprocess', ''))[:36]} — "
            f"{rows[i]['documents_count']} док. — {str(rows[i]['actor'])[:44]}"
            f"{'…' if len(str(rows[i]['actor'])) > 44 else ''}"
        ),
        key="dash_pair_drilldown",
    )
    sel = rows[ix]
    st.markdown(
        f"**Процесс:** {sel['subprocess']}  \n"
        f"**Ключ:** `{sel.get('process_key', '')}` · **ID каталога:** `{sel['process_id']}`  \n"
        f"**Актор:** {sel['actor']}"
    )
    try:
        kw: dict = {
            "actor": sel["actor"],
            "limit": 60,
            "process_group": proc_group,
            "actor_group": actor_group,
        }
        pid = sel.get("process_id")
        if pid is not None and int(pid) > 0:
            kw["process_id"] = int(pid)
        pk = sel.get("process_key")
        if pk:
            kw["process_key"] = pk
        doc_res = api_client.actor_process_documents(**kw)
    except Exception as e:
        st.error(f"Не удалось загрузить документы: {e}")
    else:
        ditems = doc_res.get("items") or []
        if not ditems:
            st.info("Нет документов для этой пары (возможно, данные изменились — обновите страницу).")
        else:
            df_doc = pd.DataFrame(
                [
                    {
                        "ID": x["document_id"],
                        "Файл": x["filename"],
                        "SHA-256": x["content_sha256"],
                        "Вклад": x["contribution"],
                    }
                    for x in ditems
                ]
            )
            st.dataframe(df_doc, width="stretch", hide_index=True)
            st.caption("Скопируйте значение из колонки SHA-256 → раздел «Документ по хэшу» в меню слева.")
