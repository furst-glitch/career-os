-- Extensions krævet af CareerOS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector til Career Memory embeddings
CREATE EXTENSION IF NOT EXISTS "pgcrypto";     -- gen_random_uuid() og kryptofunktioner
