def calculate_spam_score(email_content):
    spam_keywords = ['free', 'win', 'lottery', 'click here']
    score = 0
    for word in spam_keywords:
        if word in email_content.lower():
            score += 1.5
    return min(score, 10.0) # Max limit 10