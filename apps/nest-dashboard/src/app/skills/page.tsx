import type { Metadata } from "next";
import { listSkills, type Skill } from "@/lib/skills";
import { getSessionUser } from "@/lib/auth";
import { listAllLikes, type SkillLikeSummary } from "@/lib/likes";
import { HackathonPhases } from "@/components/hackathon-phases";
import { AuthChip } from "./auth-chip";
import { CodeBlock } from "./code-block";
import { LikeButton } from "./like-button";
import { SubmitForm } from "./submit-form";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "SkillMD — Nanda Town",
  description:
    "Teach an OpenClaw agent a new trick. Write a SkillMD, host your endpoints, and submit it here.",
};

/* ------------------------------------------------------------------ */
/*  Small presentational helpers                                       */
/* ------------------------------------------------------------------ */

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="py-10">
      {eyebrow && <p className="eyebrow mb-4">{eyebrow}</p>}
      <h2 className="mb-6 font-display text-[clamp(1.8rem,3vw,2.5rem)] leading-[1.1] tracking-tight text-ink-900">
        {title}
      </h2>
      {children}
    </section>
  );
}

function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded-md border border-cream-400/70 bg-cream-200 px-1.5 py-0.5 font-mono text-[0.85em] text-rust">
      {children}
    </code>
  );
}

const TYPE_LABEL: Record<Skill["source_type"], string> = {
  url: "Hosted link",
  github: "GitHub",
  content: "Pasted",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/* ------------------------------------------------------------------ */
/*  Example + API snippets                                             */
/* ------------------------------------------------------------------ */

const EXAMPLE_SKILL = `# Weather Lookup

Get the current weather for any city.

## Base URL
https://weather.example.com

## Endpoints

GET /weather?city={city}
  Returns the current weather for one city.
  Example:
    curl "https://weather.example.com/weather?city=Boston"
  Response:
    { "city": "Boston", "tempF": 64, "sky": "cloudy" }

## How the agent should use this
1. Ask the user which city they want.
2. Call GET /weather with that city.
3. Read tempF and sky from the answer, then tell the user.`;

const API_LIST = `# List every SkillMD
curl https://nandatown.projectnanda.org/api/skills

# Get one SkillMD
curl https://nandatown.projectnanda.org/api/skills/<id>`;

const API_POST = `curl -X POST https://nandatown.projectnanda.org/api/skills \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Weather Lookup",
    "source_type": "url",
    "source_url": "https://weather.example.com/skill.md",
    "endpoints": "GET /weather?city={city}"
  }'`;

/* ================================================================== */
/*  Page                                                               */
/* ================================================================== */

/**
 * The OAuth callbacks only ever redirect with these short codes; anything
 * else in the query string is ignored so nobody can craft a link that puts
 * their own words in our error banner.
 */
const AUTH_ERROR_MESSAGES: Record<string, string> = {
  not_configured: "Sign-in isn't configured on this server yet.",
  interrupted: "Sign-in was interrupted. Please try again.",
  rejected: "The sign-in provider rejected the request. Please try again.",
  no_identity: "The sign-in provider didn't return an identity. Please try again.",
};

export default async function SkillsPage({
  searchParams,
}: {
  searchParams: Promise<{ auth_error?: string }>;
}) {
  const [skills, likes, viewer, params] = await Promise.all([
    listSkills(),
    listAllLikes(),
    getSessionUser(),
    searchParams,
  ]);
  const authError = params.auth_error
    ? AUTH_ERROR_MESSAGES[params.auth_error]
    : undefined;

  return (
    <div className="bg-cream-100">
      {/* ---------------------------------------------------------- */}
      {/*  HERO                                                        */}
      {/* ---------------------------------------------------------- */}
      <section className="relative paper-texture border-b border-cream-400/60">
        <div className="relative mx-auto max-w-[1240px] px-6 pt-20 pb-16 sm:px-10 md:pt-24">
          <div className="mb-8 flex items-center gap-3">
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-rust" />
            <span className="eyebrow">SkillMD · for OpenClaw agents</span>
          </div>
          <h1 className="max-w-3xl font-display text-[clamp(2.4rem,5.5vw,4.2rem)] leading-[1.04] tracking-[-0.018em] text-ink-900">
            Teach an agent a <span className="italic text-ink-700">new trick.</span>
          </h1>
          <p className="mt-7 max-w-xl text-[1.12rem] leading-[1.55] text-ink-500">
            A SkillMD is a short Markdown file that tells an OpenClaw agent how
            to use your API. Write the steps, put your endpoints online, and
            drop the file in below.
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-3xl px-6 pb-24 sm:px-10">
        {/* ---------------------------------------------------------- */}
        {/*  SUBMIT FORM (moved to top of page)                          */}
        {/* ---------------------------------------------------------- */}
        <Section eyebrow="Submit it" title="Add your SkillMD">
          <p className="mb-7 text-[1.05rem] leading-[1.7] text-ink-500">
            Three ways to send it: a public link to the file, a GitHub repo, or
            paste the text. We save it to the registry so agents can find it.
          </p>
          <div className="rounded-3xl border border-cream-400/70 bg-cream-200/50 p-7 sm:p-9">
            <SubmitForm />
          </div>
        </Section>

        <div className="h-px bg-cream-400/70" />

        {/* ---------------------------------------------------------- */}
        {/*  TWO-PHASE HACKATHON BLOCK                                   */}
        {/* ---------------------------------------------------------- */}
        <section className="py-10">
          <HackathonPhases />
        </section>

        <div className="h-px bg-cream-400/70" />

        {/* ---------------------------------------------------------- */}
        {/*  WHAT IS IT                                                  */}
        {/* ---------------------------------------------------------- */}
        <Section eyebrow="The idea" title="What’s a SkillMD?">
          <p className="mb-5 text-[1.05rem] leading-[1.7] text-ink-500">
            It’s just a Markdown file. Think of it as a how-to written for an
            agent instead of a person. It says what your tool does, where it
            lives, and the steps to use it. The agent reads the file like a
            recipe card and follows along.
          </p>
          <p className="mb-8 text-[1.05rem] leading-[1.7] text-ink-500">
            A SkillMD has two parts, and you need both:
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-cream-400/70 bg-cream-50 p-6">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-rust">
                Part 1
              </p>
              <h3 className="mt-3 font-display text-[1.4rem] leading-tight text-ink-900">
                The instructions
              </h3>
              <p className="mt-2 text-[0.95rem] leading-[1.6] text-ink-500">
                The Markdown itself — what the skill does and the exact steps
                the agent should take.
              </p>
            </div>
            <div className="rounded-2xl border border-cream-400/70 bg-cream-50 p-6">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-rust">
                Part 2
              </p>
              <h3 className="mt-3 font-display text-[1.4rem] leading-tight text-ink-900">
                The endpoints
              </h3>
              <p className="mt-2 text-[0.95rem] leading-[1.6] text-ink-500">
                Your real API — live URLs the agent can actually call. The file
                points at them; they do the work.
              </p>
            </div>
          </div>
        </Section>

        <div className="h-px bg-cream-400/70" />

        {/* ---------------------------------------------------------- */}
        {/*  WHAT YOU NEED                                               */}
        {/* ---------------------------------------------------------- */}
        <Section eyebrow="Before you submit" title="What you need">
          <ol className="space-y-5">
            {[
              {
                n: "1",
                head: "A SkillMD file",
                body: (
                  <>
                    A Markdown file with a name, what it does, the base URL,
                    each endpoint, and step-by-step how the agent should use it.
                    See the example below.
                  </>
                ),
              },
              {
                n: "2",
                head: "Endpoints that are actually online",
                body: (
                  <>
                    The URLs in your file have to be real and reachable. Host
                    them somewhere that stays up — Render, Railway, Vercel, Fly,
                    or your own server. A SkillMD with dead links does nothing.
                  </>
                ),
              },
              {
                n: "3",
                head: "Test them first",
                body: (
                  <>
                    Open an endpoint in your browser or run{" "}
                    <InlineCode>curl</InlineCode>. If it doesn’t answer for you,
                    it won’t answer for the agent.
                  </>
                ),
              },
            ].map((item) => (
              <li
                key={item.n}
                className="flex gap-4 rounded-2xl border border-cream-400/70 bg-cream-50 p-6"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink-900 font-mono text-[0.85rem] text-cream-50">
                  {item.n}
                </span>
                <div>
                  <h3 className="font-display text-[1.3rem] leading-tight text-ink-900">
                    {item.head}
                  </h3>
                  <p className="mt-1.5 text-[0.95rem] leading-[1.6] text-ink-500">
                    {item.body}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </Section>

        <div className="h-px bg-cream-400/70" />

        {/* ---------------------------------------------------------- */}
        {/*  WRITE ONE                                                   */}
        {/* ---------------------------------------------------------- */}
        <Section eyebrow="Write it" title="A SkillMD, start to finish">
          <p className="mb-2 text-[1.05rem] leading-[1.7] text-ink-500">
            Here’s a whole one. Copy it, change the name and the URLs to your
            own, and you’re most of the way there.
          </p>
          <CodeBlock title="skill.md">{EXAMPLE_SKILL}</CodeBlock>
          <p className="text-[0.95rem] leading-[1.65] text-ink-500">
            Keep it short and concrete. List every endpoint the agent might
            need, show one example call and answer, and spell out the steps in
            plain words.
          </p>
        </Section>

        <div className="h-px bg-cream-400/70" />

        {/* ---------------------------------------------------------- */}
        {/*  API                                                         */}
        {/* ---------------------------------------------------------- */}
        <Section eyebrow="For agents" title="Read the registry from code">
          <p className="mb-2 text-[1.05rem] leading-[1.7] text-ink-500">
            Every submission is available over a small JSON API. An agent can
            pull the list, then fetch one skill to read its instructions.
          </p>
          <CodeBlock title="Read">{API_LIST}</CodeBlock>
          <p className="mt-6 mb-2 text-[1.05rem] leading-[1.7] text-ink-500">
            You can also register a SkillMD without the form:
          </p>
          <CodeBlock title="Register">{API_POST}</CodeBlock>
        </Section>

        <div className="h-px bg-cream-400/70" />

        {/* ---------------------------------------------------------- */}
        {/*  LIST                                                        */}
        {/* ---------------------------------------------------------- */}
        <Section
          eyebrow="The registry"
          title={`Submitted so far${skills.length ? ` · ${skills.length}` : ""}`}
        >
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-cream-400/70 bg-cream-50 px-5 py-4">
            <p className="max-w-sm text-[0.9rem] leading-[1.5] text-ink-500">
              <span className="font-semibold text-ink-700">Audience Choice:</span>{" "}
              heart your favorite submissions. Anyone can see the votes and who
              cast them; liking needs a quick sign-in so it stays bot-free.
            </p>
            <AuthChip
              viewer={
                viewer
                  ? { name: viewer.name, avatar: viewer.avatar, provider: viewer.provider }
                  : null
              }
            />
          </div>
          {authError && (
            <div className="mb-6 rounded-2xl border border-rust/40 bg-rust/10 px-5 py-3 text-[0.9rem] text-rust">
              {authError}
            </div>
          )}
          {skills.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-cream-400 bg-cream-50 p-10 text-center">
              <p className="text-[1rem] text-ink-500">
                No SkillMDs yet. Be the first.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {skills.map((skill) => (
                <SkillCard
                  key={skill.id}
                  skill={skill}
                  likes={likes[skill.id]}
                  viewer={viewer ? { sub: viewer.sub, name: viewer.name, avatar: viewer.avatar } : null}
                />
              ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Submission card                                                    */
/* ------------------------------------------------------------------ */

function SkillCard({
  skill,
  likes,
  viewer,
}: {
  skill: Skill;
  likes: SkillLikeSummary | undefined;
  viewer: { sub: string; name: string; avatar: string | null } | null;
}) {
  const tags = (skill.tags ?? "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
  const showReach = skill.source_type === "url" || skill.source_type === "github";
  // Strip provider subs before anything crosses to the client component.
  const likers = (likes?.likers ?? []).map(({ name, avatar }) => ({ name, avatar }));
  const viewerLiked = viewer ? (likes?.subs ?? []).includes(viewer.sub) : false;

  return (
    <div className="rounded-2xl border border-cream-400/70 bg-cream-50 p-6 transition-colors hover:border-ink-300">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-display text-[1.45rem] leading-tight text-ink-900">
            {skill.name}
          </h3>
          {skill.author && (
            <p className="mt-1 text-[0.85rem] text-ink-400">by {skill.author}</p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <span className="rounded-full border border-cream-400 bg-cream-200 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-ink-500">
            {TYPE_LABEL[skill.source_type]}
          </span>
          <LikeButton
            skillId={skill.id}
            initialCount={likes?.count ?? 0}
            initialLikers={likers}
            initiallyLiked={viewerLiked}
            viewer={viewer ? { name: viewer.name, avatar: viewer.avatar } : null}
          />
        </div>
      </div>

      {skill.description && (
        <p className="mt-3 text-[0.97rem] leading-[1.6] text-ink-500">
          {skill.description}
        </p>
      )}

      {skill.endpoints && (
        <pre className="mt-4 overflow-x-auto rounded-lg border border-cream-400/70 bg-cream-100 p-3 font-mono text-[0.78rem] leading-relaxed text-ink-600">
          {skill.endpoints}
        </pre>
      )}

      {tags.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={tag}
              className="rounded-md bg-cream-200 px-2 py-0.5 font-mono text-[0.72rem] text-ink-400"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-cream-400/70 pt-4 text-[0.82rem] text-ink-400">
        <span>{formatDate(skill.created_at)}</span>

        {showReach &&
          (skill.reachable ? (
            <span className="inline-flex items-center gap-1.5 text-sage">
              <span className="h-1.5 w-1.5 rounded-full bg-sage" />
              link responded
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-rust">
              <span className="h-1.5 w-1.5 rounded-full bg-rust" />
              couldn’t reach link
            </span>
          ))}

        {skill.source_url && (
          <a
            href={skill.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-rust hover:text-ink-900"
          >
            Open source ↗
          </a>
        )}
        <a
          href={`/api/skills/${skill.id}`}
          className="font-medium text-ink-500 hover:text-ink-900"
        >
          API record
        </a>
      </div>
    </div>
  );
}
