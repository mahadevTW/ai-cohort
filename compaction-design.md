1. current table structure like below,
    there session table - as of now it just tenant identifier
    chat table which is history of messages

Goal : 
As of nwo every api call is sending all messages history to OPEN ai api we want to make sure that we dont send bulk amout of data which may not be neeed
When we do cpmpaction, eventually foloup api call should only send compacted summary of conversation
-> it might happen as part of summary, we end up loosing osme information

Design : 

1. in session table ,we will keep count of size of al messages together as 1 coliumn
2. in chat table, we will keep size of each message
3. session table is just sum of this size

4. Whenever we run the compaction, all messages present in the session will be compacted and compaction result will be saved in saperate table
5. when we do compaction we will save it, 
6. we will save timestamp in compaction
7. when user sends the message, then we will look into compaction tabel,  if there is any result for given session id, we will read that along with timestamp
8. use this timestamp to read conversation history after this timestamp
9. send compaction result and trimmed conversation history to the openai api


CX behavour : 
When chat reaches X size, user will be seen an error messsage context window filled up
, we will ask user to compact,when user clicks on compact, API will be called along with session id


here X as size if sum of compacted summary + size of messages after compaction.
session_size_after_compaction
size_excluding_compaction