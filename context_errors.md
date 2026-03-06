## Voice Server Logs for using voice first then text, here I tell it my favorite color is blue, then I ask it what is my favorite color USING THE CHAT, it should remember it, but it just gives an error. 
2026-03-04 20:42:26,540 INFO sessionStart — initialising Nova Sonic stream (region=us-east-1, session_id=ef1b6cdb-9a4e-4894-bd09-034aebf413e7)
2026-03-04 20:42:26,651 INFO Nova Sonic stream ready
2026-03-04 20:42:31,336 INFO contentStart — role=USER
2026-03-04 20:42:31,336 INFO Transcription chunk: 'can you remember that my favorite color is blue'
2026-03-04 20:42:31,337 INFO contentEnd — role=USER
2026-03-04 20:42:32,284 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:32,284 INFO Assistant text chunk: "I understand that your favorite color is blue, and I'll keep that in mind for ou"
2026-03-04 20:42:32,285 INFO contentEnd — role=ASSISTANT
2026-03-04 20:42:32,420 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:33,330 INFO contentEnd — role=ASSISTANT
2026-03-04 20:42:33,330 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:33,330 INFO Assistant text chunk: " While I can't store personal preferences permanently between sessions, I'll rem"
2026-03-04 20:42:33,330 INFO contentEnd — role=ASSISTANT
2026-03-04 20:42:33,446 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:34,678 INFO contentEnd — role=ASSISTANT
2026-03-04 20:42:34,678 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:34,678 INFO Assistant text chunk: ' If you ever need color-related design suggestions or themes, just let me know— '
2026-03-04 20:42:34,680 INFO contentEnd — role=ASSISTANT
2026-03-04 20:42:34,801 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:36,475 INFO contentEnd — role=ASSISTANT
2026-03-04 20:42:37,326 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:37,326 INFO Assistant text chunk: "I understand that your favorite color is blue, and I'll keep that in mind for ou"
2026-03-04 20:42:37,326 INFO contentEnd — role=ASSISTANT
2026-03-04 20:42:43,929 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:43,929 INFO Assistant text chunk: " While I can't store personal preferences permanently between sessions, I'll rem"
2026-03-04 20:42:43,929 INFO contentEnd — role=ASSISTANT
2026-03-04 20:42:52,926 INFO contentStart — role=ASSISTANT
2026-03-04 20:42:52,926 INFO Assistant text chunk: ' If you ever need color-related design suggestions or themes, just let me know— '
2026-03-04 20:42:52,926 INFO contentEnd — role=ASSISTANT
2026-03-04 20:43:22,927 WARNING Queue timeout (30s) after assistant text — stream stalled, flushing
2026-03-04 20:43:22,927 INFO Flushing response — transcription=47 chars, response=733 chars, audio=True
2026-03-04 20:43:22,991 INFO Saved 2 messages to DynamoDB for session ef1b6cdb-9a4e-4894-bd09-034aebf413e7
2026-03-04 20:43:23,041 ERROR Response error: Invalid input request, please fix your input and try again.


## Voice Server Logs for using text first then Voice, i simply
## chatted to the AI using text telling it my favourite colour is blue and it gave me a response, then i started voice chat, and it gave me an error.

2026-03-04 20:45:50,817 INFO sessionStart — initialising Nova Sonic stream (region=us-east-1, session_id=59c9390e-b0fb-4de5-9643-825749e7fa88)
2026-03-04 20:45:50,926 INFO Nova Sonic stream ready
2026-03-04 20:45:50,928 INFO Extracted current diagram context (969 chars)
2026-03-04 20:45:51,104 INFO Injecting 2 past messages into stream for session 59c9390e-b0fb-4de5-9643-825749e7fa88
2026-03-04 20:45:51,257 ERROR Response error: RequestId=2d6ae149-6c0d-4725-96e7-694ee10d0320 : Chat history is over max limit. Trim chat history and try again.
2026-03-04 20:45:51,258 WARNING Stream ended with error: RequestId=2d6ae149-6c0d-4725-96e7-694ee10d0320 : Chat history is over max limit. Trim chat history and try again.