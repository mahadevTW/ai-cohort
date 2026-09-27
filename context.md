2 Tables

## Saving the conversation history:
1. conversation
    1. conversation_id
    2. title
    3. created_at

2. messages
    1. id
    2. conversation_id FK(conversation)
    3. message_text
    4. role [ENUM]  - > system, assitant, user, developer
    5. created_at

DB Layer
functions:
1. create_conversation(title)
2. save_message(conversation_id, message_text, role)
3. list_all_messages(conversation_id) --> all messages in given conversation
 - Write tests using pytest for All db layer functions
4. list_conversation --> return all the conversations along with the date title


APIs:
1. create conversation
    1. post api for create converdsation
    2. Save it in conversation table and return newly created ID
    3. From UI, when user clicks on New COnversation Button, it should open new TAB, and let user type the message and once user clicks on send, fire this api and wait for response
    4. Once response is recibved then call the /chat API with new conversation ID and message text

    5. other way to do this is - > on click on New COnversation let user type the message and fire the /chat api and inside chat api Backend service layer if conversation id not received then create new conversation

2. Incremental changes in Chat API:
    1. Whenever message is received from user, 1st thing it should do is insert it into messages table against conversation id and text with role as user and created at also
    2. When LLM responds back for the question being sent, before you respond back to consunmers save the response into tale - > role should be assitant

=====================================================================
make model remember:
1. Model does not remember anything
2. ANything you want model to know , you should it inside the request

Change:

    1. Before sending message to llm read conversation history from Db and then send it
=========================================================================================

## Saving the cost

1. Because we have started sendong so many messages in api call
     - TPken cost
     - request slow down
     - NW bytes consumption

2. Create summarization logic via which
    1. before you send message to LLM, count how much token it is consuming
    2. if request tokens has reached the X threshold
    3. Trigger summay job which will take all message from start to current and make api call to LLM
    4. LLM will respond with summary
        5. Save summary in table
        6. ALong with summary save timestamp at which summary is being calculated
    5. When new message comes, dont read all the messages
    read summary + all messages after summarization is done
    6. Send summary+ messages + current message to llm

This concept overall is called a compaction of context



