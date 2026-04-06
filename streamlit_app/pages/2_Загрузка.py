import pandas as pd
import streamlit as st

import api_client
from streamlit_app.ui_guard import require_api

st.set_page_config(page_title="Загрузка", layout="wide")
st.title("Загрузка документа")

require_api()


def _status_ru(status: str) -> str:
    return {
        "ok": "Успешно",
        "processing": "Обрабатывается",
        "error": "Ошибка",
    }.get(status, status)


def _render_history_table() -> None:
    try:
        docs = api_client.list_documents()
    except Exception as e:
        st.error(f"Не удалось загрузить список: {e}")
        return

    if not docs:
        st.info("Пока нет загруженных документов — после отправки файла строка появится здесь и сохранится при обновлении страницы.")
        return

    rows = []
    for d in docs:
        err = d.get("error_message") or ""
        if len(err) > 200:
            err = err[:200] + "…"
        sha = d.get("content_sha256") or ""
        rows.append(
            {
                "ID": d["id"],
                "Файл": d["filename"],
                "SHA-256": sha,
                "Статус": _status_ru(d.get("status") or ""),
                "Загружен": d.get("uploaded_at") or "",
                "Обработан": d.get("processed_at") or "",
                "Сущности": d.get("entity_count", 0),
                "Связи": d.get("relation_count", 0),
                "Цепочки": d.get("chain_count", 0),
                "Сообщение": err,
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


st.subheader("История загрузок")
st.caption(
    "Список берётся с сервера: после перезагрузки страницы видно очередь и итоговый статус каждого файла. "
    "Колонка **SHA-256** — для страницы «Документ по хэшу» (скопируйте значение ячейки)."
)

if hasattr(st, "fragment"):
    @st.fragment(run_every=4)
    def _history_fragment() -> None:
        _render_history_table()

    _history_fragment()
else:
    _render_history_table()
    if st.button("Обновить список"):
        st.rerun()

st.divider()
st.subheader("Удалить документ из базы")
st.caption(
    "Удаляется запись документа и все связанные данные (сущности, связи, цепочки, совпадения с процессами). "
    "Файл на диске не хранится — только метаданные и результаты анализа."
)
try:
    _docs_for_delete = api_client.list_documents()
except Exception as e:
    st.warning(f"Не удалось загрузить список для удаления: {e}")
    _docs_for_delete = []

if _docs_for_delete:
    _labels = [
        f"#{d['id']} — {d['filename']} ({_status_ru(d.get('status') or '')})"
        for d in _docs_for_delete
    ]
    _id_by_label = {lbl: d["id"] for lbl, d in zip(_labels, _docs_for_delete)}
    _pick = st.selectbox("Выберите документ", options=_labels, key="delete_doc_pick")
    _confirm = st.checkbox("Подтверждаю безвозвратное удаление", key="delete_doc_confirm")
    if st.button("Удалить выбранный документ", type="secondary"):
        if not _confirm:
            st.warning("Отметьте подтверждение.")
        else:
            _did = _id_by_label[_pick]
            try:
                api_client.delete_document(_did)
            except Exception as e:
                st.error(f"Не удалось удалить: {e}")
            else:
                st.success(f"Документ #{_did} удалён.")
                st.rerun()
else:
    st.info("Нет документов для удаления.")

st.divider()
st.subheader("Новая загрузка")

up = st.file_uploader("Файл (docx, pdf, txt)", type=["docx", "pdf", "txt"])
st.caption(
    "На сервере файл **не уходит в OpenRouter как файл**: из docx/pdf извлекается **текст** "
    "(таблицы в docx включаются), затем в модель идёт только этот текст. "
    "Для сложных docx при установленном LibreOffice можно принудительно: **DOCX_READ_VIA_PDF=1** на процессе API."
)
force = st.checkbox("Пересчитать, даже если такой файл уже есть (по SHA-256)", value=False)

if st.button("Отправить на анализ", type="primary"):
    if not up:
        st.warning("Выберите файл.")
    else:
        data = up.getvalue()
        try:
            res = api_client.upload_file(data, up.name, force=force)
        except Exception as e:
            st.error(f"Ошибка API: {e}")
        else:
            status = res.get("status")
            doc = res.get("document") or {}
            doc_id = doc.get("id")
            pstat = doc.get("processing_status")

            if status == "accepted":
                st.success(
                    f"Файл принят в очередь (документ **#{doc_id}**). "
                    "Обработка идёт на сервере — статус в таблице выше обновится автоматически."
                )
            elif status == "reused":
                st.info(
                    "Такой файл уже был успешно обработан. Включите «Пересчитать, даже если такой файл уже есть», чтобы отправить его на анализ снова."
                )
            elif status == "already_processing":
                st.warning(f"Этот файл уже в обработке (документ **#{doc_id}**). Дождитесь завершения или обновите страницу.")
            elif status == "error":
                st.error(doc.get("error_message") or "Ошибка при приёме или обработке.")
            else:
                st.json(res)

            if pstat == "ok" and doc.get("content_sha256"):
                st.info(
                    f"SHA-256: `{doc.get('content_sha256')}` — для страницы «Документ по хэшу»."
                )
