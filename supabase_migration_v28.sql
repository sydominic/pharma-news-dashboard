-- v28 / v1.34 migration: article summary + content-aware classification fields
-- 기존 Supabase 테이블이 이미 있는 경우 이 파일만 SQL Editor에서 실행하면 됩니다.

alter table public.news_articles add column if not exists article_summary text;
alter table public.news_articles add column if not exists article_text text;
alter table public.news_articles add column if not exists sub_tags text;
alter table public.news_articles add column if not exists classification_reason text;
alter table public.news_articles add column if not exists classification_score text;
alter table public.news_articles add column if not exists body_fetch_status text;

create index if not exists idx_news_articles_body_fetch_status on public.news_articles (body_fetch_status);
