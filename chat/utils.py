import pandas as pd
import re

def analyze_and_format_chat(messages_data):
    """
    Takes a list of message dictionaries.
    Uses Pandas to aggressively filter stopwords ("Caveman Mode") 
    to maximize token efficiency for the AI.
    """
    if not messages_data:
        return "No messages found."

    # 1. Create DataFrame
    df = pd.DataFrame(messages_data)

    # 2. Basic Cleaning
    required_cols = ['author__username', 'content', 'timestamp']
    if not all(col in df.columns for col in required_cols):
        return "Error: Data structure mismatch."

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')

    # --- PANDAS ANALYSIS (Real Stats) ---
    total_messages_all_time = len(df)
    
    # Calculate participation before filtering
    if not df.empty:
        # Exclude System and AI from "Active Participants" count
        real_users = df[~df['author__username'].isin(['System', 'AI'])]
        user_counts = real_users['author__username'].value_counts()
        active_users = ", ".join(user_counts.index.tolist())
    else:
        active_users = "None"

    # --- TOKEN OPTIMIZATION STRATEGY ---
    
    # 1. LIMIT CONTEXT: Last 50 messages
    recent_df = df.tail(50).copy()

    # 2. STOPWORDS LIST (Common English fillers)
    # Removing these keeps the meaning but cuts tokens by ~40%
    STOPWORDS = {
        "the", "is", "at", "which", "on", "a", "an", "and", "or", "but", 
        "if", "then", "else", "when", "how", "what", "why", "who", "of", 
        "to", "in", "for", "with", "by", "from", "up", "down", "out", 
        "so", "my", "your", "his", "her", "its", "our", "their", "this", 
        "that", "these", "those", "am", "are", "was", "were", "be", "been", 
        "being", "have", "has", "had", "do", "does", "did", "can", "could", 
        "should", "would", "may", "might", "must", "im", "i'm", "ill", "i'll",
        "hey", "hi", "hello", "sup", "yo", "yeah", "yes", "no", "nah", "ok", "okay",
        "bro", "dude", "man", "like", "just", "really", "very", "actually"
    }

    def optimize_content(row):
        user = row['author__username']
        content = str(row['content'])
        
        # A. AGGRESSIVE FILTERING
        if user == 'AI':
            return "[AI]" # Minimal placeholder
        
        if user == 'System':
            return None # Drop completely
            
        # B. TEXT CLEANING ("Caveman Mode")
        # 1. Lowercase
        content = content.lower()
        # 2. Remove punctuation (keep $ for money and numbers)
        content = re.sub(r'[^\w\s\$]', '', content) 
        # 3. Tokenize
        words = content.split()
        # 4. Filter Stopwords
        meaningful_words = [w for w in words if w not in STOPWORDS]
        
        if not meaningful_words:
            return None # Drop empty messages
            
        return " ".join(meaningful_words)

    # Apply optimization
    recent_df['optimized_content'] = recent_df.apply(optimize_content, axis=1)
    
    # Drop rows that became empty (System messages or just stopwords)
    recent_df = recent_df.dropna(subset=['optimized_content'])

    # 3. TRANSCRIPT GENERATION (Merging & Time Gaps)
    transcript_lines = []
    
    current_user = None
    current_block = []
    last_timestamp = None

    for _, row in recent_df.iterrows():
        user = row['author__username']
        content = row['optimized_content']
        timestamp = row['timestamp']

        # Time Gap (Gap > 1 hour)
        if last_timestamp:
            time_diff = (timestamp - last_timestamp).total_seconds() / 3600
            if time_diff > 1.0:
                if current_user:
                    full_msg = " ".join(current_block)
                    transcript_lines.append(f"{current_user}:{full_msg}")
                    current_user = None
                    current_block = []
                # Minimal Gap Marker
                transcript_lines.append(f"|GAP {int(time_diff)}H|")

        # Merge
        if user == current_user:
            current_block.append(content)
        else:
            if current_user:
                full_msg = " ".join(current_block)
                # Format: "user:word word word"
                transcript_lines.append(f"{current_user}:{full_msg}")
            
            current_user = user
            current_block = [content]
        
        last_timestamp = timestamp

    # Final Flush
    if current_user:
        full_msg = " ".join(current_block)
        transcript_lines.append(f"{current_user}:{full_msg}")
    
    transcript_text = "\n".join(transcript_lines)

    # 4. Final Prompt
    ai_context = f"""
    STATS: Users:{active_users} | Msgs:{total_messages_all_time}
    LOG:
    {transcript_text}
    """

    return ai_context