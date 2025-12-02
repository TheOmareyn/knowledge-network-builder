-- Knowledge Network Builder Database Schema

CREATE TABLE IF NOT EXISTS User (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_premium INTEGER DEFAULT 0,
    is_admin INTEGER DEFAULT 0,
    api_calls_today INTEGER DEFAULT 0,
    api_calls_reset_date DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS Document (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    title TEXT,
    author TEXT,
    year TEXT,
    publisher TEXT,
    journal TEXT,
    volume TEXT,
    number TEXT,
    pages TEXT,
    publication_type TEXT,
    category TEXT,
    doctrine TEXT,
    page_count INTEGER,
    is_private INTEGER DEFAULT 0,
    upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES User (id)
);

CREATE TABLE IF NOT EXISTS KnowledgeEntry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    proof TEXT NOT NULL,
    page_number INTEGER,
    FOREIGN KEY (document_id) REFERENCES Document (id)
);

CREATE TABLE IF NOT EXISTS ConsistencyCheck (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    book1_id INTEGER NOT NULL,
    book2_id INTEGER NOT NULL,
    book1_answer TEXT NOT NULL,
    book2_answer TEXT NOT NULL,
    contradiction_percentage INTEGER NOT NULL,
    checked_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book1_id) REFERENCES Document (id),
    FOREIGN KEY (book2_id) REFERENCES Document (id),
    UNIQUE(question, book1_id, book2_id)
);