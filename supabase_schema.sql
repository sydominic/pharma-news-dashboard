-- Pharma News Dashboard Supabase cache schema
-- Supabase SQL Editor에서 1회 실행하세요.

create table if not exists public.news_articles (
  uid text primary key,
  published_at timestamptz,
  date text,
  time text,
  source text,
  category text,
  keywords text,
  importance text,
  qa_flag boolean default false,
  title text,
  summary text,
  article_summary text,
  article_text text,
  sub_tags text,
  classification_reason text,
  classification_score text,
  body_fetch_status text,
  link text,
  rss_query_name text,
  rss_query text,
  collected_at text,
  cache_updated_at timestamptz default now()
);

-- v1.34/v28 migration for existing tables.
alter table public.news_articles add column if not exists article_summary text;
alter table public.news_articles add column if not exists article_text text;
alter table public.news_articles add column if not exists sub_tags text;
alter table public.news_articles add column if not exists classification_reason text;
alter table public.news_articles add column if not exists classification_score text;
alter table public.news_articles add column if not exists body_fetch_status text;

create index if not exists idx_news_articles_published_at on public.news_articles (published_at desc);
create index if not exists idx_news_articles_category on public.news_articles (category);
create index if not exists idx_news_articles_source on public.news_articles (source);
create index if not exists idx_news_articles_importance on public.news_articles (importance);
create index if not exists idx_news_articles_body_fetch_status on public.news_articles (body_fetch_status);

create table if not exists public.collection_log (
  id text primary key,
  status text,
  added_count integer default 0,
  total_count integer default 0,
  error_message text,
  collected_at timestamptz default now()
);

-- 필요 시 RLS를 켜고 service_role key만 서버에서 사용하세요.
-- Streamlit Secrets에는 service_role 또는 insert/upsert 권한이 있는 key를 넣어야 합니다.
