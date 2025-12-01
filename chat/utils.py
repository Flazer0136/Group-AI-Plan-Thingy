def prepare_conversation_context(messages_data, max_messages=30):
    """
    Smart context preparation:
    - Keep recent messages in full
    - Summarize patterns, not individual words
    - Maintain conversation flow
    """
    if not messages_data:
        return []
    
    # Sort by timestamp
    sorted_messages = sorted(messages_data, key=lambda x: x['timestamp'])
    
    # Get recent messages (last 30)
    recent_messages = sorted_messages[-max_messages:]
    
    # Build role-based conversation (like we had before!)
    conversation = []
    
    for msg in recent_messages:
        username = msg['author__username']
        content = msg['content']
        
        # Skip system messages for AI context
        if username == 'System':
            continue
        
        if username == 'AI':
            conversation.append({
                'role': 'model',
                'content': content
            })
        else:
            conversation.append({
                'role': 'user',
                'content': f"{username}: {content}"
            })
    
    return conversation
