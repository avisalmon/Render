# babook.co.il — Feature Skeleton

## Overview

Based on market research, here's a feature skeleton organized by Avi's 5 scopes:

---

## Scope 1: Training (3 Levels)

### 1.1 User Level — Beginners (Chatting, Prompts, Vibe Coding)

**Purpose:** Onboard non-technical users to AI fundamentals

**Features:**
- **Guided courses:**
  - "AI for Everyone" (ChatGPT intro)
  - "Prompting 101" (prompt engineering)
  - "Vibe Coding 101" (AI-assisted coding from natural language)
  - Duration: 2-4 hours each, video-based

- **Interactive labs:**
  - ChatGPT/Claude playground (sandboxed, no coding needed)
  - Prompt refinement tools (A/B test prompts)
  - Vibe code generator (describe in English → working code)

- **Community:**
  - Forums: "Getting Started" + "Prompt Tips"
  - Peer feedback on prompts

- **Gamification:**
  - Points for completing lessons
  - Badge: "Prompt Engineer" (100+ points)

---

### 1.2 Practical Level — Practitioners (Co-coding, MCP, GitHub Copilot, AutoAgents)

**Purpose:** Build production AI tools and integrations

**Features:**
- **Structured skill tracks:**
  - "Co-Coding with GitHub Copilot" (4 weeks, hands-on)
  - "MCP Server Development" (6 weeks)
  - "Building AI Agents with Claude/AutoGPT" (8 weeks)
  - "LangChain & LLM Apps" (6 weeks)
  - "Prompt Engineering for Production" (3 weeks)

- **Project-based labs:**
  - Clone-along: Build a customer support chatbot (GitHub Copilot-assisted)
  - Build your first MCP: Custom tools for code analysis
  - Deploy a multi-agent system to production
  - Fine-tune an open model on custom data

- **Tools & IDE:**
  - Cloud IDE (Replit-like, but customized)
  - GitHub Copilot integration (resold seats)
  - Access to sandbox APIs (OpenAI, Anthropic, open models)

- **Community:**
  - Project showcase (code + demo links)
  - Code review forum ("Review my MCP")
  - Skill store: "Post your expertise" (advisors, code reviews)

- **Gamification:**
  - Project leaderboard (stars, forks, reviews)
  - Badge: "MCP Developer", "Agent Builder"
  - Seasonal hackathons (weekly/monthly)

---

### 1.3 Deep Level — Researchers (Torch, Transformers, Fine-tuning, Training)

**Purpose:** Train/fine-tune custom models, understand internals

**Features:**
- **Research courses:**
  - "Transformers: From Scratch" (PyTorch + math, 12 weeks)
  - "Fine-Tuning & LoRA" (practical, 6 weeks)
  - "Training Large Language Models" (theory + distributed training, 12 weeks)
  - "Constitutional AI & RLHF" (advanced, 8 weeks)
  - "Research Paper Implementation" (reading → coding, ongoing)

- **Lab environment:**
  - GPU compute (shared or paid instances)
  - Jupyter notebooks with pre-loaded Hugging Face models
  - Integration with Weights & Biases (experiment tracking)
  - Access to cloud training infrastructure (AWS, GCP, Azure)

- **Datasets & benchmarks:**
  - Curated datasets (10+ research-quality datasets)
  - Benchmark leaderboards (custom tasks)
  - Peer evaluation (research rigor)

- **Community:**
  - Research papers discussion forum
  - Weekly ML arxiv digest
  - Research mentorship (advisors help review ideas)

- **Outputs:**
  - Publish to model hub (Hugging Face mirror)
  - Conference preprint submission support
  - Co-author recognition on blog

---

## Scope 2: Community

### 2.1 Forums

**Structure:**
- Categories by skill level (Beginner, Practitioner, Researcher)
- Categories by topic (ChatGPT, Coding, Fine-tuning, Research)
- Pinned resources & FAQs
- User reputation system (upvotes, accepted answers)

**Moderation:**
- Community guidelines
- Automated spam detection
- Staff + community moderators

**Features:**
- Q&A format with accepted answer
- Discussion threads with voting
- Media uploads (code, screenshots)
- Notifications on replies

### 2.2 Skill Store

**Purpose:** Marketplace for peer learning + revenue share

**Model:**
- **Skill = short course/tutorial (2-20 hours)**
  - e.g., "Fine-tune GPT-2 in 1 hour", "Build a Telegram bot with Claude", "Prompt injection attacks explained"
- **Creator revenue:** 70% of price, babook.co.il takes 30%
- **Price range:** ₪50-500 (≈$15-150)

**Features:**
- Skill landing page (title, description, prerequisites, outcomes)
- Free preview video (5 min)
- Structured modules (video + lab + quiz)
- Student feedback & ratings
- Creator analytics (students, revenue, reviews)

**Moderation:**
- Quality review before listing
- Community reports (low-quality content)
- Refund policy (30-day money-back)

---

### 2.3 Newsletters

**Cadence:**
- **Weekly digest** (Sunday): "This week in AI"
  - Top stories from news + community
  - Featured tutorials from skill store
  - Upcoming meetups

- **Monthly deep-dive** (1st of month): "AI research roundup"
  - Top papers from arxiv
  - Community research highlights
  - Interview with advisor/expert

**Engagement:**
- Subscriber-only extras (early access to courses, advisor Q&A)
- Sponsorships (NVIDIA, OpenAI, Hugging Face)

---

### 2.4 Meetups (Virtual + Physical)

**Virtual:**
- Weekly live coding sessions (1 hour, Thursday 7 PM UTC)
- Monthly AMA (Ask Me Anything) with experts
- Quarterly conference (4-6 hour online event)

**Physical (Israel-focused):**
- Monthly meetups in Tel Aviv, Jerusalem, Haifa
- Quarterly workshops
- Annual babook conference (2-day, Tel Aviv)

**Features:**
- Event registration + calendar
- Live stream + recording archive
- Networking with other attendees
- Sponsor booths (AI companies hiring)

---

### 2.5 Solutions Hub

**Purpose:** Curated answers to common problems

**Format:**
- Solution = worked example + code + explanation
  - e.g., "How to handle token limits in long conversations"
  - "Recovering from prompt injection attacks"
  - "Optimizing cost for high-volume API usage"

**Structure:**
- Solution templates (problem → causes → solutions)
- Tagging (topic, difficulty, language)
- Community upvoting
- Official solutions (staff-reviewed)

---

## Scope 3: Token Provider (Copilot/Credits/MCP)

### 3.1 GitHub Copilot Resale

**Business model:**
- Negotiate bulk rates with GitHub
- Resell seats to users at margin (₪149-199/mo vs GitHub ₪200+)
- Add value: education + community support

**Features:**
- Billing dashboard (seat usage, cost tracking)
- Integration with babook course recommendations
- Group team pricing

---

### 3.2 OpenAI API Credits Store

**Model:**
- Pre-purchase credit bundles (₪100, ₪500, ₪1000)
- 5-10% discount vs direct purchase
- Trackable via babook dashboard

**Features:**
- Credit balance dashboard
- Usage tracking (tokens by model)
- Automatic alerts (80%, 100% usage)
- Spending insights (cost per project)

---

### 3.3 MCP Server Marketplace

**Purpose:** Sell custom tools & integrations

**Model:**
- Developers publish MCP servers on babook
- Users subscribe (₪20-100/mo per server)
- Revenue share: 70/30 (developer/babook)

**Examples:**
- "PDF Analyzer MCP" — extract data from PDFs
- "Web Scraper MCP" — crawl websites safely
- "Custom Database MCP" — SQL tool for private databases

**Features:**
- MCP listing page (docs, pricing, ratings)
- One-click installation guide
- API key management
- Developer analytics (subscribers, usage)

---

## Scope 4: Service Store (Advisory, Lecturers Hub)

### 4.1 Advisor Marketplace

**Offering:**
- 1-on-1 consultations (30-90 min)
- Code review sessions
- Career advice
- Project brainstorming

**Advisors:**
- Vetted professionals (GitHub stars, publications, industry experience)
- Categories: AI Engineering, ML Research, Product Strategy
- Badge system (1⭐ to 5⭐ based on reviews)

**Pricing:**
- Range: ₪300-1000/hour (~$85-280)
- babook takes 20-30% commission
- Calendar booking + Zoom integration

---

### 4.2 Lecturers Hub

**Offering:**
- Corporate training (on-site or virtual)
- Custom curriculum development
- Workshop facilitation

**Services:**
- "AI Fundamentals for your team" (tailored to company)
- "Prompt engineering bootcamp"
- "LLM applications in production"

**Engagement:**
- Lead capture (companies request quotes)
- babook matches with lecturers
- Commission: 15-25% per deal

---

### 4.3 Hiring Board

**Features:**
- Job listings from AI companies
- Resume showcase (build portfolio on babook)
- Company profiles (culture, tech stack)
- Sponsored postings (companies pay for visibility)

---

## Scope 5: Additional Features

### 5.1 User Profiles & Portfolio

**Profile:**
- Public portfolio (courses completed, projects, publications)
- Skill badges (earned from courses)
- Endorsements (peers can endorse skills)
- Link to GitHub, LinkedIn

**Project showcase:**
- Embed GitHub repos
- Demo videos
- Write-ups
- Community stars/comments

---

### 5.2 Messaging & Networking

**Direct messaging:**
- Chat with advisors, fellow learners
- Group chats for cohorts (course-based)

**Discovery:**
- "Find collaborators" (filter by skill, interest)
- "Find mentors" (search advisors)

---

### 5.3 API Documentation

**babook API:**
- Embed babook courses on partner sites
- Query user progress programmatically
- Webhook notifications (course completion)
- Custom integrations for corporate clients

---

## Implementation Phases

### Phase 1 (MVP) — Practical Level + Forums
- 3-5 structured skills tracks (6-8 weeks each)
- Community forums (categories, Q&A)
- Project showcase
- Gamification (points, badges)
- Skill store (launch with 10-20 creator skills)

### Phase 2 — User Level + Tokens
- Beginner video courses
- GitHub Copilot resale
- OpenAI credit store
- Newsletter

### Phase 3 — Deep Level + Services
- Researcher courses (PyTorch, fine-tuning)
- Advisor marketplace
- MCP server marketplace
- Meetups (virtual only first)

### Phase 4 — Scale
- Physical meetups
- Hiring board
- Corporate training
- Lecturers hub
- Annual conference

---

## Success Metrics (Draft)

| Metric | Target (Year 1) |
|--------|-----------------|
| Active users | 5,000 |
| Paid subscribers | 500 |
| Forum posts | 10,000+ |
| Published skills | 50+ |
| Advisor revenue (total) | ₪200K |
| Token resale volume | ₪500K |

---

## Next Steps

1. **Narrow scope:** Which of the 5 is the priority?
2. **Validate:** Survey potential users (beginners vs practitioners vs researchers)
3. **Set roadmap:** Which features MVP? Which Phase 1?
4. **Define success:** What does "good" look like for each scope?
