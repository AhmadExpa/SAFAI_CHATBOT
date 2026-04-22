from fastapi import HTTPException
from fastapi.responses import StreamingResponse

def stream_openai_chat(client, model_name, messages):
    def event_stream():
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,  # Pass the full history here!
            stream=True
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    try:
        return StreamingResponse(event_stream(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))