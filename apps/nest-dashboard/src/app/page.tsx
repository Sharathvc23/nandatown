import type { ReactNode } from 'react';

/* ------------------------------------------------------------------ */
/*  Copy — sourced verbatim from the project one-pager.                 */
/*  Edit the doc, then mirror it here; do not reword in place.          */
/* ------------------------------------------------------------------ */

const REPO_URL = 'https://github.com/projnanda/nandatown';
const SITE_URL = 'https://nandatown.projectnanda.org';

const P1_LEDE = `Nanda Town contains protocols for AI agents, built by different people and companies, that offer their services through SkillMDs and can find each other, prove who they are, build trust, work together, and pay each other.`;

const P2 = `Everything in the town runs on twelve protocol layers. They cover transport, communication, identity, registry, auth, trust, payments, coordination, negotiation, memory, privacy, and data facts. Together, these layers work like a town's city council. Every interaction between agents follows rules set by one of these layers, so the council has to get the town's foundations right before the town can open for real business. Each layer has a working default version in the public Apache 2.0 repository.`;

const P3 = `Today, Nanda Town is a sandbox where those rules get built and tested. The plan is for it to grow into a live town where deployed agents provide real services through their registered SkillMDs. To get there, the communication layer needs a concrete agent-to-agent implementation, and which framework carries it (A2A, LangChain, CrewAI, or something else) is still an open question. That implementation will run alongside the interaction protocols and plugins that people have already contributed through pull requests, and once those pieces are in place, the town can run on its own.`;

const P4 = `Because this is the base version that everyone else will build on, it has to be as close to perfect as possible, so its protocols are constantly tested against attacks, bad actors, and hostile simulations. The main job for contributors is to identify gaps in the protocol layers by finding situations where current rules handle poorly, and then fill each gap with a fix for that layer. A contributor who finds a problem that fits no existing layer can propose a new layer.`;

const P5 = `The standard Nanda Town is also kept plain on purpose. It has no company rules, no industry assumptions, and no policy of its own. That way, anyone can clone or fork it and create their own sandbox on top of it. A hospital network, a bank, or an online marketplace can each run their own town under their own rules while still speaking the same protocols as everyone else. Nanda Town itself becomes the standard test rig those protocols and services are proven on.`;

const P6_DEVELOPERS = `Developers get involved by sending GitHub pull requests. A pull request usually carries a protocol, which is the set of rules for one kind of interaction between agents, together with a plugin, which is the code that runs those rules inside one of the twelve layers, and a test that proves the new protocol holds up. Developers can also publish an agent skill as a SkillMD, which is a short Markdown file that any agent deployed in Nanda Town can read and follow.`;

const P6_COMPANIES = `Companies get involved by contributing the protocols or services for their own industry or by running a town of their own built on the Nanda Town sandbox.`;

const P7 = `The end goal is a set of protocols reliable enough that an agent can show up in any town it has never seen and be found, trusted, put to work, and paid without any custom integration.`;

const P8_INTRO = `Two examples show how open and decentralized this really is.`;

const P8_DEVELOPER = `Suppose a developer sends a pull request to the main repository and the core team closes it, either for a technical or conceptual reason. That developer does not need anyone's permission to keep going. The repository carries the Apache 2.0 license, so they can fork or clone github.com/projnanda/nandatown, add their protocol and its plugin, the same two pieces their pull request contained, and release the result under their own name as a “Better Nanda Town” if they believe it is one.`;

const P8_COMPANY = `Or suppose a company wants a town/sandbox tailored to its own ecosystem, where it controls the rules. It starts from the base Nanda Town, which carries the protocols the core team has tested hardest alongside the protocols they made, tailored for their specific town/sandbox.`;

const P8_CLOSING = `Nanda Town remains the foundation, and any number of towns/sandboxes can grow out of it.`;

const LAYERS = [
  'Transport',
  'Communication',
  'Identity',
  'Registry',
  'Auth',
  'Trust',
  'Payments',
  'Coordination',
  'Negotiation',
  'Memory',
  'Privacy',
  'Data facts',
];

const NO_POLICY_ITEMS = [
  'No company rules',
  'No industry assumptions',
  'No policy of its own',
];

/* ------------------------------------------------------------------ */
/*  Rich text — linkifies repo/site mentions, bolds exact phrases       */
/* ------------------------------------------------------------------ */

const LINK_TARGETS: Record<string, string> = {
  'github.com/projnanda/nandatown': REPO_URL,
  'nandatown.projectnanda.org': SITE_URL,
};

const LINK_RE = /(github\.com\/projnanda\/nandatown|nandatown\.projectnanda\.org)/g;

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function Rich({ text, bold = [] }: { text: string; bold?: string[] }) {
  const boldRe = bold.length
    ? new RegExp(`(${bold.map(escapeRegExp).join('|')})`, 'g')
    : null;

  const renderPlain = (chunk: string, key: string): ReactNode => {
    if (!boldRe) return <span key={key}>{chunk}</span>;
    return (
      <span key={key}>
        {chunk.split(boldRe).map((seg, i) =>
          bold.includes(seg) ? (
            <strong key={i} className="font-semibold text-ink-900">
              {seg}
            </strong>
          ) : (
            seg
          ),
        )}
      </span>
    );
  };

  return (
    <>
      {text.split(LINK_RE).map((part, i) =>
        LINK_TARGETS[part] ? (
          <a
            key={i}
            href={LINK_TARGETS[part]}
            target={part.startsWith('github') ? '_blank' : undefined}
            rel={part.startsWith('github') ? 'noreferrer' : undefined}
            className="text-rust underline decoration-rust/40 underline-offset-4 hover:decoration-rust transition-colors"
          >
            {part}
          </a>
        ) : (
          renderPlain(part, `t${i}`)
        ),
      )}
    </>
  );
}

function RepoButton({ dark = false }: { dark?: boolean }) {
  return (
    <a
      href={REPO_URL}
      target="_blank"
      rel="noreferrer"
      className={
        dark
          ? 'inline-flex items-center rounded-md bg-cream-50 text-ink-900 px-5 py-2.5 text-[0.9rem] font-medium hover:bg-cream-200 transition-colors'
          : 'btn-primary'
      }
    >
      github.com/projnanda/nandatown &rarr;
    </a>
  );
}

/* ================================================================== */
/*  Page                                                               */
/* ================================================================== */

export default function Home() {
  return (
    <div className="bg-cream-100">
      {/* ============================================================ */}
      {/*  HERO — paragraph 1                                            */}
      {/* ============================================================ */}
      <section className="relative paper-texture">
        <div className="relative mx-auto max-w-[1240px] px-6 sm:px-10 pt-20 pb-20 md:pt-24 md:pb-24">
          <h1 className="font-display animate-fade-in max-w-[24ch] text-[clamp(2.1rem,4.8vw,4rem)] leading-[1.08] tracking-[-0.016em] text-ink-900">
            An open-source sandbox where anyone can{' '}
            <span className="italic text-ink-700">
              build and test protocols and services
            </span>{' '}
            for AI agents.
          </h1>

          <div className="mt-10 grid gap-10 lg:grid-cols-[1.5fr_1fr] lg:items-start">
            <p className="animate-fade-in stagger-2 text-[1.1rem] leading-[1.65] text-ink-600">
              <Rich
                text={P1_LEDE}
                bold={[
                  'find each other, prove who they are, build trust, work together, and pay each other',
                ]}
              />
            </p>

            <div className="animate-fade-in stagger-3 lg:pt-2">
              <RepoButton />
              <dl className="mt-10 grid grid-cols-2 gap-6 border-t border-cream-400/70 pt-6">
                <Stat label="Protocol layers" value="12" />
                <Stat label="License" value="Apache 2.0" />
              </dl>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  TWELVE PROTOCOL LAYERS — paragraph 2                          */}
      {/* ============================================================ */}
      <section className="border-t border-cream-400/70 bg-cream-50">
        <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-20 md:py-24">
          <div className="grid gap-12 lg:grid-cols-[1.1fr_1fr] lg:items-start">
            <div>
              <p className="eyebrow">12 protocol layers</p>
              <h2 className="font-display mt-5 text-[clamp(1.9rem,3.6vw,3rem)] leading-[1.08] tracking-[-0.015em] text-ink-900">
                These layers work like<br />
                <span className="italic text-ink-700">a town&rsquo;s city council.</span>
              </h2>
              <p className="mt-7 text-[1.05rem] leading-[1.7] text-ink-500">
                <Rich
                  text={P2}
                  bold={[
                    'twelve protocol layers',
                    "work like a town's city council",
                  ]}
                />
              </p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-px bg-cream-400/50 border border-cream-400/50 rounded-2xl overflow-hidden self-start">
              {LAYERS.map((layer, i) => (
                <div key={layer} className="bg-cream-50 p-5">
                  <span className="font-mono text-[10px] tracking-[0.2em] text-ink-300">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <p className="mt-2 font-display text-[1.15rem] leading-tight text-ink-900">
                    {layer}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  TODAY / AS CLOSE TO PERFECT — paragraphs 3 and 4              */}
      {/* ============================================================ */}
      <section className="border-t border-cream-400/70">
        <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-20 md:py-24">
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-cream-400/70 bg-cream-200 p-8 sm:p-10">
              <p className="eyebrow">Today</p>
              <p className="mt-6 text-[1.02rem] leading-[1.7] text-ink-600">
                <Rich
                  text={P3}
                  bold={[
                    'a sandbox where those rules get built and tested',
                    'grow into a live town',
                    'still an open question',
                  ]}
                />
              </p>
            </div>

            <div className="rounded-2xl border border-cream-400/70 bg-cream-200 p-8 sm:p-10">
              <p className="eyebrow">As close to perfect as possible</p>
              <p className="mt-6 text-[1.02rem] leading-[1.7] text-ink-600">
                <Rich
                  text={P4}
                  bold={[
                    'the base version that everyone else will build on',
                    'identify gaps in the protocol layers',
                    'propose a new layer',
                  ]}
                />
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  KEPT PLAIN ON PURPOSE — paragraph 5                           */}
      {/* ============================================================ */}
      <section className="border-t border-cream-400/70 bg-cream-50">
        <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-20 md:py-24">
          <div className="grid gap-12 lg:grid-cols-[1fr_1.3fr] lg:items-start">
            <div>
              <p className="eyebrow">Kept plain on purpose</p>
              <div className="mt-8 space-y-3">
                {NO_POLICY_ITEMS.map((item) => (
                  <div
                    key={item}
                    className="rounded-xl border border-cream-400/70 bg-cream-100 px-6 py-4"
                  >
                    <p className="font-display text-[1.25rem] text-ink-900">{item}</p>
                  </div>
                ))}
              </div>
            </div>

            <p className="text-[1.05rem] leading-[1.7] text-ink-500 lg:pt-1">
              <Rich
                text={P5}
                bold={[
                  'kept plain on purpose',
                  'clone or fork it and create their own sandbox on top of it',
                  'the standard test rig',
                ]}
              />
            </p>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  GET INVOLVED — paragraph 6, split at its own sentence break   */}
      {/* ============================================================ */}
      <section className="border-t border-cream-400/70">
        <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-20 md:py-24">
          <p className="eyebrow">Get involved</p>
          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-cream-400/70 bg-cream-200 p-8 sm:p-10">
              <h3 className="font-display text-[1.9rem] leading-tight text-ink-900">
                Developers
              </h3>
              <p className="mt-5 text-[1.02rem] leading-[1.7] text-ink-600">
                <Rich
                  text={P6_DEVELOPERS}
                  bold={[
                    'sending GitHub pull requests',
                    'a protocol',
                    'a plugin',
                    'a test that proves the new protocol holds up',
                    'publish an agent skill as a SkillMD',
                  ]}
                />
              </p>
            </div>

            <div className="rounded-2xl border border-cream-400/70 bg-cream-200 p-8 sm:p-10">
              <h3 className="font-display text-[1.9rem] leading-tight text-ink-900">
                Companies
              </h3>
              <p className="mt-5 text-[1.02rem] leading-[1.7] text-ink-600">
                <Rich
                  text={P6_COMPANIES}
                  bold={[
                    'contributing the protocols or services for their own industry',
                    'running a town of their own',
                  ]}
                />
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  THE END GOAL — paragraph 7                                    */}
      {/* ============================================================ */}
      <section className="border-t border-cream-400/70 bg-ink-900 text-cream-50">
        <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-20 md:py-28">
          <p className="eyebrow text-cream-200/70">The end goal</p>
          <p className="font-display mt-8 max-w-[30ch] text-[clamp(1.7rem,3.6vw,3rem)] leading-[1.18] tracking-[-0.01em]">
            {P7}
          </p>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  TWO EXAMPLES — paragraph 8, split at its own sentence breaks  */}
      {/* ============================================================ */}
      <section className="border-t border-cream-400/70 bg-cream-50">
        <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-20 md:py-24">
          <h2 className="font-display max-w-[26ch] text-[clamp(1.8rem,3.4vw,2.8rem)] leading-[1.1] tracking-[-0.012em] text-ink-900">
            {P8_INTRO}
          </h2>

          <div className="mt-12 grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-cream-400/70 bg-cream-100 p-8 sm:p-10">
              <p className="eyebrow">A developer</p>
              <p className="mt-5 text-[1.02rem] leading-[1.7] text-ink-600">
                <Rich
                  text={P8_DEVELOPER}
                  bold={[
                    "does not need anyone's permission to keep going",
                    'Apache 2.0 license',
                    '“Better Nanda Town”',
                  ]}
                />
              </p>
            </div>

            <div className="rounded-2xl border border-cream-400/70 bg-cream-100 p-8 sm:p-10">
              <p className="eyebrow">A company</p>
              <p className="mt-5 text-[1.02rem] leading-[1.7] text-ink-600">
                <Rich
                  text={P8_COMPANY}
                  bold={['where it controls the rules']}
                />
              </p>
            </div>
          </div>

          <p className="font-display mt-14 max-w-[36ch] text-[1.6rem] leading-[1.3] text-ink-900">
            {P8_CLOSING}
          </p>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  CTA                                                           */}
      {/* ============================================================ */}
      <section className="border-t border-cream-400/70 bg-ink-900 text-cream-50">
        <div className="mx-auto max-w-[1240px] px-6 sm:px-10 py-16 md:py-20 flex flex-wrap items-center justify-between gap-8">
          <p className="font-display text-[clamp(1.6rem,3vw,2.4rem)] leading-tight">
            github.com/projnanda/nandatown
          </p>
          <RepoButton dark />
        </div>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Stat                                                                */
/* ------------------------------------------------------------------ */

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-mono text-[10px] uppercase tracking-[0.22em] text-ink-300">
        {label}
      </dt>
      <dd className="mt-2 font-display text-[1.65rem] leading-none text-ink-900">
        {value}
      </dd>
    </div>
  );
}
