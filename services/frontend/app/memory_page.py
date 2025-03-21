import gradio as gr
import pandas as pd
import os
from shared import cc, parse_datetime


def clear(input_message):
    return ""


def create_dataframe(query=None, start_date=None, end_date=None):
    start_datetime_obj = parse_datetime(start_date)
    end_datetime_obj = parse_datetime(end_date)

    if query:
        query_answers = cc.rag.retrieve_multiple(
            query_texts=[query],
            start_date_time=start_datetime_obj,
            end_date_time=end_datetime_obj,
        )
        ids, documents, metadata, distances = query_answers[0]
        df = pd.DataFrame(
            {
                "ids": ids,
                "documents": documents,
                "filename": [e["filename"] for e in metadata],
                "date_time": [e.get("date_time", "N/A") for e in metadata],
                "distances": [round(e, 2) for e in distances],
            }
        )
        # sort by distance
        df = df.sort_values(by="distances", ascending=False)
        return df
    else:
        # Get all documents, possibly filtered by date
        ids, documents, metadata = cc.db_api.get_full_database(
            start_date_time=start_datetime_obj, end_date_time=end_datetime_obj
        )
        df = pd.DataFrame(
            {
                "ids": ids,
                "documents": documents,
                "filename": [e["filename"] for e in metadata],
                "date_time": [e.get("date_time", "N/A") for e in metadata],
            }
        )
        return df


def filter_by_date(start_date, end_date):
    start_datetime_obj = parse_datetime(start_date)
    end_datetime_obj = parse_datetime(end_date)
    return create_dataframe(None, start_datetime_obj, end_datetime_obj)


def handle_audio_upload(file):
    if file is None:
        return "Please upload a WAV file"

    if not file.name.lower().endswith(".wav"):
        return "Only WAV files are supported"

    try:
        cc.transcribe_and_store(file.name)
        return f"Audio stored in DB."
    except Exception as e:
        return f"Error processing file: {str(e)}"


# Memory page implementation
with gr.Blocks() as demo:
    with gr.Sidebar(open=False):
        gr.Markdown("# ")
        gr.Markdown("# Upload additional data")
        file_upload = gr.File(
            label="Upload Audio (.wav)",
            file_types=[".wav"],
            type="filepath",
            file_count="single",
        )
        upload_status = gr.Textbox(label="Upload Status", interactive=False)

    with gr.Row():
        query = gr.Textbox(
            label="Query",
            lines=1,
            placeholder="Insert some query you want to search for...",
        )

    with gr.Row():
        start_date = gr.DateTime(label="Start Date", value=None)
        end_date = gr.DateTime(label="End Date", value=None)

    data_view = gr.DataFrame(create_dataframe, wrap=True)

    with gr.Row():
        btn_show_all = gr.Button("Show All")
        btn_filter_by_date = gr.Button("Filter by Date")
        btn_clear_dates = gr.Button("Clear Date Filters")
        gr.Button("Clear Database (Not yet implemented)")

    # Add audio player for selected files
    with gr.Row():
        selected_audio = gr.Audio(
            label="Audio Player", type="filepath", interactive=False
        )

    # Function to handle row selection and play audio
    def on_select_audio(evt: gr.SelectData, data):
        selected_row = data.iloc[evt.index[0]]
        filename = selected_row.get("filename")
        session_id = filename.split("_")[0]
        date = filename.split("_")[2]
        directory = f"audio/recordings_{date}_{session_id}/snippets"
        # Prepend /data directory to the path
        if filename:
            filename = os.path.join(directory, os.path.basename(filename))
        return filename

    # Connect DataFrame selection to audio player
    data_view.select(fn=on_select_audio, inputs=[data_view], outputs=[selected_audio])

    # Add file upload handler
    file_upload.upload(
        fn=handle_audio_upload,
        inputs=[file_upload],
        outputs=[upload_status],
    ).then(create_dataframe, [], [data_view])

    query.submit(
        fn=create_dataframe,
        inputs=[query, start_date, end_date],
        outputs=[data_view],
        queue=False,
    ).then(clear, [query], [query])

    # Date filter buttons
    btn_show_all.click(create_dataframe, outputs=[data_view])
    btn_filter_by_date.click(
        filter_by_date, inputs=[start_date, end_date], outputs=[data_view]
    )
    btn_clear_dates.click(lambda: (None, None), outputs=[start_date, end_date]).then(
        create_dataframe, [], [data_view]
    )
