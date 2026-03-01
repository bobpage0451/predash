# Dashboard

The dashboard is a **Next.js 16** web application that provides a UI for viewing and exploring processed email data, managing **desired actions**, and viewing **action matches** against your emails.

## Tech Stack

- **Next.js 16** with App Router
- **React 19**
- **TypeScript 5**
- **Tailwind CSS v4**

## Setup

```bash
cd /workspace/apps/dashboard
npm install
```

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start development server with hot reload |
| `npm run build` | Create optimised production build |
| `npm run start` | Run the production build |
| `npm run lint` | Run ESLint |

## Project Structure

```
apps/dashboard/
├── app/
│   ├── layout.tsx              # Root layout
│   ├── page.tsx                # Home page (two-column: sidebar + feed)
│   ├── globals.css             # Global styles
│   ├── api/
│   │   ├── posts/              # Email feed API
│   │   ├── stories/            # Story feed API
│   │   ├── desired-actions/    # CRUD for desired actions
│   │   │   ├── route.ts        # GET (list) + POST (create + inline embed)
│   │   │   └── [id]/route.ts   # DELETE + PATCH (toggle active)
│   │   └── action-matches/
│   │       └── route.ts        # GET (list matches)
│   └── favicon.ico
├── components/
│   ├── EmailCard.tsx           # Email post card
│   ├── StoryCard.tsx           # Story card
│   ├── TabNav.tsx              # Tab navigation
│   ├── DesiredActionsSidebar.tsx # Left sidebar with action cards
│   └── AddActionModal.tsx      # Modal for creating desired actions
├── lib/
│   └── db.ts                   # PostgreSQL connection pool
├── public/                     # Static assets
├── next.config.ts              # Next.js configuration
├── tsconfig.json               # TypeScript configuration
├── postcss.config.mjs          # PostCSS / Tailwind
├── eslint.config.mjs           # ESLint configuration
└── package.json
```

## API Routes

| Route | Method | Description |
|---|---|---|
| `/api/posts` | GET | Paginated list of processed emails |
| `/api/stories` | GET | Paginated list of extracted stories |
| `/api/desired-actions` | GET | List desired actions with match counts |
| `/api/desired-actions` | POST | Create a desired action (auto-embeds via Ollama) |
| `/api/desired-actions/[id]` | DELETE | Remove a desired action |
| `/api/desired-actions/[id]` | PATCH | Toggle `active` status |
| `/api/action-matches` | GET | List action matches (optional `?action_id=` filter) |

## Features

- **Email Feed** — Browse processed emails as cards
- **Story Feed** — Browse LLM-extracted stories with tags and topics
- **Desired Actions Sidebar** — Define actions you're looking for (e.g. "Tommy Hilfiger jacket on sale") and see which emails match
- **Action Matching** — Automatic similarity-based matching using pgvector embeddings, with optional action type filtering
