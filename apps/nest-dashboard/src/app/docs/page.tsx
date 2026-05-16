'use client';

import { useState, useEffect, useCallback } from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface TocItem {
  id: string;
  label: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const TOC: TocItem[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'tiers', label: 'Tier 1 vs Tier 2' },
  { id: 'installation', label: 'Installation' },
  { id: 'first-experiment', label: 'Your First Experiment' },
  { id: 'scenarios', label: 'Scenario YAML Reference' },
  { id: 'layers', label: 'The 12 Layers' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'templates', label: 'Agent Templates' },
  { id: 'plugins', label: 'Writing a Plugin' },
  { id: 'cli', label: 'CLI Reference' },
  { id: 'faq', label: 'FAQ' },
];

/* ------------------------------------------------------------------ */
/*  CopyButton                                                         */
/* ------------------------------------------------------------------ */

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className="absolute top-3 right-3 rounded-md border border-warm-700 bg-warm-800 px-2.5 py-1 text-xs font-medium text-warm-300 transition-all hover:bg-warm-700 hover:text-warm-100"
      aria-label="Copy to clipboard"
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  CodeBlock                                                          */
/* ------------------------------------------------------------------ */

function CodeBlock({
  children,
  title,
}: {
  children: string;
  title?: string;
}) {
  return (
    <div className="group relative my-4 overflow-hidden rounded-xl border border-warm-800 bg-warm-900">
      {title && (
        <div className="border-b border-warm-800 bg-warm-950 px-4 py-2 text-xs font-medium text-warm-400">
          {title}
        </div>
      )}
      <CopyButton text={children} />
      <pre className="overflow-x-auto p-4 pr-20 text-sm leading-relaxed text-warm-200">
        <code className="font-mono">{children}</code>
      </pre>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  TerminalBlock                                                      */
/* ------------------------------------------------------------------ */

function TerminalBlock({ children }: { children: string }) {
  return (
    <div className="group relative my-4 overflow-hidden rounded-xl border border-warm-800 bg-warm-950">
      <div className="flex items-center gap-2 border-b border-warm-800 bg-warm-900 px-4 py-2.5">
        <span className="h-3 w-3 rounded-full bg-red-500/80" />
        <span className="h-3 w-3 rounded-full bg-yellow-500/80" />
        <span className="h-3 w-3 rounded-full bg-green-500/80" />
        <span className="ml-2 text-xs text-warm-500">Terminal</span>
      </div>
      <pre className="overflow-x-auto p-4 text-sm leading-relaxed text-green-400">
        <code className="font-mono">{children}</code>
      </pre>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  InlineCode                                                         */
/* ------------------------------------------------------------------ */

function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded-md border border-warm-200 bg-warm-100 px-1.5 py-0.5 text-sm font-mono text-crimson">
      {children}
    </code>
  );
}

/* ------------------------------------------------------------------ */
/*  Section wrapper                                                    */
/* ------------------------------------------------------------------ */

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24 py-12 first:pt-8">
      <h2 className="mb-6 text-2xl font-bold tracking-tight text-warm-900 sm:text-3xl">
        {title}
      </h2>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Sidebar                                                            */
/* ------------------------------------------------------------------ */

function Sidebar({
  activeId,
  open,
  onClose,
}: {
  activeId: string;
  open: boolean;
  onClose: () => void;
}) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed top-16 left-0 z-50 h-[calc(100vh-4rem)] w-64 transform border-r border-warm-200
          bg-white/95 backdrop-blur-md transition-transform duration-300 ease-in-out
          lg:sticky lg:z-10 lg:translate-x-0 lg:border-r lg:bg-white/80
          ${open ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <nav className="h-full overflow-y-auto px-5 py-8">
          <p className="mb-5 text-xs font-semibold uppercase tracking-widest text-warm-400">
            Documentation
          </p>
          <ul className="space-y-0.5">
            {TOC.map((item) => {
              const isActive = activeId === item.id;
              return (
                <li key={item.id}>
                  <a
                    href={`#${item.id}`}
                    onClick={onClose}
                    className={`
                      flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-all
                      ${
                        isActive
                          ? 'bg-crimson/10 text-crimson'
                          : 'text-warm-500 hover:bg-warm-50 hover:text-warm-900'
                      }
                    `}
                  >
                    {isActive && (
                      <span className="mr-2.5 h-1.5 w-1.5 rounded-full bg-crimson" />
                    )}
                    {item.label}
                  </a>
                </li>
              );
            })}
          </ul>

          <div className="mt-8 rounded-xl border border-warm-200 bg-warm-50 p-4">
            <p className="text-xs font-semibold text-warm-700">Need help?</p>
            <p className="mt-1 text-xs leading-relaxed text-warm-500">
              Open an issue on{' '}
              <a
                href="https://github.com/mariagorskikh/nest/issues"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-crimson hover:underline"
              >
                GitHub
              </a>
              .
            </p>
          </div>
        </nav>
      </aside>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  FAQ Item                                                           */
/* ------------------------------------------------------------------ */

function FaqItem({
  question,
  answer,
}: {
  question: string;
  answer: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-warm-200 last:border-b-0">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between py-5 text-left"
      >
        <span className="text-base font-semibold text-warm-900">
          {question}
        </span>
        <svg
          className={`h-5 w-5 shrink-0 text-warm-400 transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="pb-5 text-sm leading-relaxed text-warm-600">
          {answer}
        </div>
      )}
    </div>
  );
}

/* ================================================================== */
/*  Page                                                               */
/* ================================================================== */

export default function DocsPage() {
  const [activeId, setActiveId] = useState('overview');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const ids = TOC.map((t) => t.id);
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter(Boolean) as HTMLElement[];

    if (elements.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => {
            const aIdx = ids.indexOf(a.target.id);
            const bIdx = ids.indexOf(b.target.id);
            return aIdx - bIdx;
          });

        if (visible.length > 0) {
          setActiveId(visible[0].target.id);
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0 },
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <div className="relative min-h-screen bg-white">
      {/* Mobile menu button */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="fixed bottom-6 left-6 z-50 flex h-12 w-12 items-center justify-center rounded-full border border-warm-200 bg-white shadow-lg transition-transform hover:scale-105 lg:hidden"
        aria-label="Open navigation"
      >
        <svg
          className="h-5 w-5 text-warm-700"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M4 6h16M4 12h16M4 18h16"
          />
        </svg>
      </button>

      <Sidebar
        activeId={activeId}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content */}
      <div className="lg:ml-64">
        <div className="mx-auto max-w-3xl px-6 pb-24 lg:px-12">
          {/* Hero — compact */}
          <div className="pb-8 pt-10">
            <h1 className="text-3xl font-bold tracking-tight text-warm-950 sm:text-4xl">
              NEST Documentation
            </h1>
            <p className="mt-3 text-base leading-relaxed text-warm-500">
              Install, configure, and run multi-agent simulations.
            </p>
          </div>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  Overview                                            */}
          {/* ================================================== */}
          <Section id="overview" title="Overview">
            <p className="mb-4 text-base leading-relaxed text-warm-600">
              NEST (Network Environment for Swarm Testing) is a sandbox for
              testing how AI agents interact with each other. You define a
              scenario in YAML&mdash;agents, roles, protocol layers, failure
              conditions&mdash;and NEST runs the simulation, recording every
              message in a JSONL trace you can inspect and replay.
            </p>
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              NEST is built at MIT Media Lab as part of Project NANDA. It is
              open-source research software (Apache 2.0).
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              {[
                {
                  title: 'Researchers',
                  desc: 'Study emergent behavior, coordination failures, and trust dynamics with full observability.',
                },
                {
                  title: 'Protocol Designers',
                  desc: 'Stress-test your agent protocol with configurable failure injection and deterministic replay.',
                },
                {
                  title: 'Developers',
                  desc: 'Build and debug multi-agent systems with JSONL traces, metrics, and HTML reports.',
                },
                {
                  title: 'Students',
                  desc: 'Learn about agent coordination, game theory, and multi-agent interaction hands-on.',
                },
              ].map((card) => (
                <div
                  key={card.title}
                  className="rounded-xl border border-warm-200 bg-warm-50/50 p-5"
                >
                  <p className="font-semibold text-warm-900">{card.title}</p>
                  <p className="mt-1.5 text-sm leading-relaxed text-warm-500">
                    {card.desc}
                  </p>
                </div>
              ))}
            </div>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  Tier 1 vs Tier 2                                   */}
          {/* ================================================== */}
          <Section id="tiers" title="Tier 1 vs Tier 2">
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              NEST has two simulation tiers. They share the same scenario format,
              the same 12 protocol layers, and the same trace output&mdash;they
              differ in what drives agent decisions.
            </p>

            <div className="grid gap-6 sm:grid-cols-2">
              {/* Tier 1 */}
              <div className="rounded-xl border-2 border-warm-200 p-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-warm-900 text-xs font-bold text-white">
                    1
                  </span>
                  <h3 className="text-lg font-bold text-warm-900">
                    Tier 1: Deterministic
                  </h3>
                </div>
                <p className="text-sm leading-relaxed text-warm-600 mb-4">
                  Agents are state machines with hard-coded rules.
                  Same seed = identical trace, every time.
                </p>
                <ul className="space-y-2 text-sm text-warm-600">
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-emerald-600 font-bold">+</span>
                    <span><strong>Reproducible:</strong> same seed produces identical output, bit-for-bit</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-emerald-600 font-bold">+</span>
                    <span><strong>Fast:</strong> 10,000+ agents on a laptop, sub-second runs</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-emerald-600 font-bold">+</span>
                    <span><strong>Free:</strong> no API keys, no internet, no cost per run</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-emerald-600 font-bold">+</span>
                    <span><strong>Isolates protocol logic:</strong> when something fails, it&rsquo;s the protocol, not the LLM</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-amber-600 font-bold">&minus;</span>
                    <span>Agents follow fixed rules; no creativity or adaptation</span>
                  </li>
                </ul>
                <div className="mt-4 rounded-lg bg-warm-50 border border-warm-200 px-4 py-3">
                  <p className="text-xs font-semibold text-warm-700 mb-1">Use Tier 1 to:</p>
                  <ul className="text-xs text-warm-500 space-y-1">
                    <li>- Validate protocol correctness before adding LLMs</li>
                    <li>- Run large-scale (1000+) simulations quickly</li>
                    <li>- Reproduce bugs deterministically</li>
                    <li>- Test failure injection (message drops, partitions)</li>
                  </ul>
                </div>
              </div>

              {/* Tier 2 */}
              <div className="rounded-xl border-2 border-crimson/20 p-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-crimson text-xs font-bold text-white">
                    2
                  </span>
                  <h3 className="text-lg font-bold text-warm-900">
                    Tier 2: LLM-Backed
                  </h3>
                </div>
                <p className="text-sm leading-relaxed text-warm-600 mb-4">
                  Agents are backed by GPT-4, Claude, or any OpenAI-compatible
                  endpoint. They receive the scenario context as a system prompt
                  and decide what to do each tick.
                </p>
                <ul className="space-y-2 text-sm text-warm-600">
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-emerald-600 font-bold">+</span>
                    <span><strong>Realistic:</strong> agents make decisions like real AI systems</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-emerald-600 font-bold">+</span>
                    <span><strong>Emergent behavior:</strong> agents can surprise you</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-emerald-600 font-bold">+</span>
                    <span><strong>Custom prompts:</strong> YAML templates control each agent&rsquo;s personality</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-amber-600 font-bold">&minus;</span>
                    <span><strong>Non-deterministic:</strong> different runs yield different traces</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-amber-600 font-bold">&minus;</span>
                    <span><strong>Costs money:</strong> each agent turn is an API call</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-0.5 text-amber-600 font-bold">&minus;</span>
                    <span><strong>Slow:</strong> limited by API latency and rate limits (10-100 agents)</span>
                  </li>
                </ul>
                <div className="mt-4 rounded-lg bg-crimson/5 border border-crimson/10 px-4 py-3">
                  <p className="text-xs font-semibold text-warm-700 mb-1">Use Tier 2 to:</p>
                  <ul className="text-xs text-warm-500 space-y-1">
                    <li>- Test how LLMs behave in multi-agent protocols</li>
                    <li>- Benchmark different models on the same scenario</li>
                    <li>- Study emergent coordination and strategic behavior</li>
                    <li>- Evaluate prompt engineering for agent roles</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="mt-6 rounded-xl border border-warm-200 bg-warm-50 p-5">
              <p className="text-sm leading-relaxed text-warm-600">
                <strong>Recommended workflow:</strong> Start with Tier 1 to
                validate your scenario and protocol logic, then switch to Tier 2 by
                changing <InlineCode>brain: state-machine</InlineCode> to{' '}
                <InlineCode>brain: llm</InlineCode> in your YAML. Everything else
                stays the same&mdash;same layers, same metrics, same trace format.
              </p>
            </div>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  Installation                                       */}
          {/* ================================================== */}
          <Section id="installation" title="Installation">
            <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-5 py-3">
              <p className="text-sm text-amber-800">
                <strong>Note:</strong> NEST is not yet published to PyPI. Install
                from the Git repository as shown below.
              </p>
            </div>

            <h3 className="mb-3 text-lg font-semibold text-warm-800">
              Prerequisites
            </h3>
            <ul className="mb-6 list-inside list-disc space-y-1 text-base text-warm-600">
              <li>
                <strong>Python 3.12+</strong> &mdash; check with{' '}
                <InlineCode>python --version</InlineCode>
              </li>
              <li>
                <strong>uv</strong> (recommended) or <strong>pip</strong> &mdash;{' '}
                <InlineCode>pip install uv</InlineCode>
              </li>
            </ul>

            <h3 className="mb-3 text-lg font-semibold text-warm-800">
              Clone and install
            </h3>
            <CodeBlock>
{`git clone https://github.com/mariagorskikh/nest.git
cd nest
uv sync`}
            </CodeBlock>

            <p className="mb-4 text-sm text-warm-600">
              This installs all 7 workspace packages (nest-core, nest-cli,
              nest-shell, nest-sdk, nest-mocks, nest-plugins-reference,
              nest-scenarios) in a single virtual environment.
            </p>

            <h3 className="mb-3 text-lg font-semibold text-warm-800">
              Verify your installation
            </h3>
            <CodeBlock>uv run nest doctor</CodeBlock>

            <TerminalBlock>
{`$ uv run nest doctor
NEST CLI v0.1.0
Python ......... 3.12.4  ok
Runtime ........ ok       ok
Plugins ........ 12/12    ok
Scenarios ...... 6 found  ok

All checks passed.`}
            </TerminalBlock>

            <h3 className="mb-3 mt-6 text-lg font-semibold text-warm-800">
              For Tier 2 (LLM agents)
            </h3>
            <p className="mb-3 text-sm text-warm-600">
              If you want to run LLM-backed agents, set your API key:
            </p>
            <CodeBlock>
{`# OpenAI
export OPENAI_API_KEY="sk-..."

# or Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."`}
            </CodeBlock>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  Your First Experiment                               */}
          {/* ================================================== */}
          <Section id="first-experiment" title="Your First Experiment">
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              Run a marketplace simulation end-to-end in three steps. 50 buyers
              and 50 sellers negotiate prices over 10 rounds.
            </p>

            <div className="mb-8">
              <div className="flex items-center gap-3 mb-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-crimson text-xs font-bold text-white">
                  1
                </span>
                <h3 className="text-lg font-semibold text-warm-800">
                  Run the scenario
                </h3>
              </div>
              <CodeBlock>uv run nest run scenarios/marketplace.yaml</CodeBlock>
              <p className="mt-2 text-sm text-warm-500">
                This creates the agents, runs the simulation, and writes
                the trace to <InlineCode>traces/marketplace.jsonl</InlineCode>.
              </p>
            </div>

            <div className="mb-8">
              <div className="flex items-center gap-3 mb-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-crimson text-xs font-bold text-white">
                  2
                </span>
                <h3 className="text-lg font-semibold text-warm-800">
                  Inspect the trace
                </h3>
              </div>
              <CodeBlock>uv run nest inspect traces/marketplace.jsonl</CodeBlock>
              <p className="mt-2 text-sm text-warm-500">
                Shows a summary of every event: sends, receives, drops,
                per-agent stats, and timing.
              </p>
            </div>

            <div className="mb-8">
              <div className="flex items-center gap-3 mb-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-crimson text-xs font-bold text-white">
                  3
                </span>
                <h3 className="text-lg font-semibold text-warm-800">
                  Generate an HTML report
                </h3>
              </div>
              <CodeBlock>uv run nest report traces/marketplace.jsonl -o report.html</CodeBlock>
              <p className="mt-2 text-sm text-warm-500">
                Produces an HTML page with delivery rate, deal rate, latency,
                throughput, per-agent breakdown, and event summary.
              </p>
            </div>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  Scenario YAML Reference                             */}
          {/* ================================================== */}
          <Section id="scenarios" title="Scenario YAML Reference">
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              A scenario YAML defines everything about a simulation run. Here
              is a complete, annotated example matching the actual schema.
            </p>

            <CodeBlock title="scenarios/marketplace.yaml">
{`name: marketplace
description: "50 buyers and 50 sellers trading products."

tier: 1                           # 1 = state-machine, 2 = LLM
seed: 42                          # RNG seed (deterministic replay)

agents:
  count: 100                      # Total agent count
  brain: state-machine            # "state-machine" or "llm"
  # llm_provider: openai          # For Tier 2: openai or anthropic
  # llm_model: gpt-4o-mini        # For Tier 2: model name
  roles:
    - name: buyer
      count: 50
    - name: seller
      count: 50

layers:                           # Plugin name for each protocol layer
  transport: in_memory
  comms: nest_native
  identity: did_key
  registry: in_memory
  auth: jwt
  trust: score_average
  payments: prepaid_credits
  coordination: contract_net
  negotiation: alternating_offers
  memory: blackboard
  privacy: noop
  datafacts: datafacts_v1

task:
  type: marketplace               # Scenario type
  config:
    rounds: 10                    # Scenario-specific config

failures:                         # Failure injection
  message_drop: 0.0              # 0.0 = no drops, 0.1 = 10% drop rate
  byzantine_agents: 0.0          # Fraction of agents that garble messages
  # network_partition:            # Split agents into isolated groups
  #   groups: [["buyer-0"], ["seller-0"]]

duration: "ticks: 10000"          # Max simulation ticks

metrics:                          # Which metrics to compute
  - delivery_rate
  - deal_rate
  - mean_latency
  - message_count
  - agent_count

output:
  trace: ./traces/marketplace.jsonl
  # report: ./reports/marketplace.html  # Optional HTML report`}
            </CodeBlock>

            <h3 className="mb-4 mt-8 text-lg font-semibold text-warm-800">
              Available scenarios
            </h3>
            <div className="overflow-x-auto rounded-xl border border-warm-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-warm-200 bg-warm-50">
                    <th className="px-4 py-3 text-left font-semibold text-warm-900">
                      File
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-warm-900">
                      Description
                    </th>
                    <th className="hidden px-4 py-3 text-left font-semibold text-warm-900 md:table-cell">
                      Agents
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-warm-100">
                  {[
                    ['marketplace.yaml', 'Buyers and sellers negotiate prices', '50 buyers + 50 sellers'],
                    ['auction.yaml', 'Sealed-bid auction with auctioneer', '1 auctioneer + 49 bidders'],
                    ['voting.yaml', 'Proposer, voters, and coordinator', '1 proposer + 20 voters + 1 coordinator'],
                    ['consensus.yaml', 'Leader-based quorum voting', '1 leader + 19 followers'],
                    ['supply_chain.yaml', '4-hop supply chain pipeline', 'supplier, manufacturer, distributor, retailer'],
                    ['reputation.yaml', 'Honest and malicious traders with observer', '6 honest + 2 malicious + 1 observer'],
                  ].map(([name, desc, agents]) => (
                    <tr key={name} className="hover:bg-warm-50/50 transition-colors">
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-sm text-crimson">
                        {name}
                      </td>
                      <td className="px-4 py-3 text-warm-600">{desc}</td>
                      <td className="hidden px-4 py-3 text-warm-500 md:table-cell">
                        {agents}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  The 12 Layers                                      */}
          {/* ================================================== */}
          <Section id="layers" title="The 12 Layers">
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              NEST organizes agent capabilities into 12 protocol layers. Each
              layer has a default reference implementation you can swap out.
              Agents access layers via{' '}
              <InlineCode>ctx.plugins.get(&quot;layer_name&quot;)</InlineCode>.
            </p>

            <div className="overflow-x-auto rounded-xl border border-warm-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-warm-200 bg-warm-50">
                    <th className="px-4 py-3 text-left font-semibold text-warm-900">
                      Layer
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-warm-900">
                      What it does
                    </th>
                    <th className="hidden px-4 py-3 text-left font-semibold text-warm-900 md:table-cell">
                      Default
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-warm-100">
                  {[
                    ['Transport', 'Moves messages between agents', 'in_memory'],
                    ['Comms', 'Structures message formats', 'nest_native'],
                    ['Identity', 'Assigns and verifies agent identities', 'did_key'],
                    ['Registry', 'Agent discovery and service lookup', 'in_memory'],
                    ['Auth', 'Authentication and permissions', 'jwt'],
                    ['Trust', 'Calculates and updates reputation scores', 'score_average'],
                    ['Payments', 'Virtual currency balance and transfers', 'prepaid_credits'],
                    ['Coordination', 'Orchestrates multi-agent workflows', 'contract_net'],
                    ['Negotiation', 'Runs negotiation protocols', 'alternating_offers'],
                    ['Memory', 'Stores and retrieves agent memory', 'blackboard'],
                    ['Privacy', 'Enforces data-sharing boundaries', 'noop'],
                    ['Data Facts', 'Validates and attests to data claims', 'datafacts_v1'],
                  ].map(([layer, what, plugin]) => (
                    <tr key={layer} className="hover:bg-warm-50/50 transition-colors">
                      <td className="whitespace-nowrap px-4 py-3 font-semibold text-warm-900">
                        {layer}
                      </td>
                      <td className="px-4 py-3 text-warm-600">{what}</td>
                      <td className="hidden px-4 py-3 font-mono text-xs text-crimson md:table-cell">
                        {plugin}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-4 text-sm text-warm-500">
              Currently, the marketplace scenario uses registry, identity,
              trust, and payments layers. Other scenarios use the layers
              passively (they&rsquo;re resolved but agents don&rsquo;t yet
              call them). Wiring more scenarios to use layers is in progress.
            </p>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  Metrics                                             */}
          {/* ================================================== */}
          <Section id="metrics" title="Metrics">
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              NEST computes metrics from the JSONL trace after each run. Specify
              which metrics you want in the scenario YAML. There is no single
              &ldquo;composite score&rdquo;&mdash;each metric measures something
              specific.
            </p>

            <div className="overflow-x-auto rounded-xl border border-warm-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-warm-200 bg-warm-50">
                    <th className="px-4 py-3 text-left font-semibold text-warm-900">
                      Metric
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-warm-900">
                      What it measures
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-warm-100">
                  {[
                    ['delivery_rate', 'Fraction of sent messages that were received. 100% in Tier 1 with no message drops.'],
                    ['deal_rate', 'Percentage of buy requests that resulted in a trade (sold:). Marketplace/auction only.'],
                    ['rejection_rate', 'Percentage of buy requests that were rejected. Marketplace only.'],
                    ['mean_rounds_to_deal', 'Average negotiation rounds before a successful trade.'],
                    ['mean_latency', 'Average time (ticks) between a send and its correlated receive.'],
                    ['message_count', 'Total number of send + receive events in the trace.'],
                    ['dropped_count', 'Number of messages dropped by failure injection.'],
                    ['agent_count', 'Number of distinct agents that participated.'],
                    ['duration', 'Time span from first to last event (ticks).'],
                    ['throughput', 'Messages per tick across all agents.'],
                    ['unique_pairs', 'Number of unique agent pairs that exchanged messages.'],
                  ].map(([name, desc]) => (
                    <tr key={name} className="hover:bg-warm-50/50 transition-colors">
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-sm text-crimson">
                        {name}
                      </td>
                      <td className="px-4 py-3 text-warm-600">{desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  Agent Templates                                     */}
          {/* ================================================== */}
          <Section id="templates" title="Agent Templates (Tier 2)">
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              Templates are YAML files that define LLM-backed agent behavior:
              system prompt, provider, model, and parameters. They&rsquo;re only
              used in Tier 2 scenarios.
            </p>

            <CodeBlock title="templates/agents/marketplace-buyer.yaml">
{`name: marketplace-buyer
description: "Buyer agent for marketplace scenarios."
provider: openai
model: gpt-4o-mini
temperature: 0.7
max_tokens: 256
system_prompt: |
  You are a buyer in a marketplace simulation.

  ACTION: send
  TO: <agent-id>
  MESSAGE: <message-content>

  Rules:
  - Send buy:<product>:<price> to purchase.
  - If rejected, increase your offer or try another seller.`}
            </CodeBlock>

            <h3 className="mb-3 mt-6 text-lg font-semibold text-warm-800">
              CLI commands
            </h3>
            <CodeBlock>
{`uv run nest templates list              # List all templates
uv run nest templates show <name>       # View a template
uv run nest templates create <name>     # Create from scratch
uv run nest templates duplicate <src> <dest>  # Copy and modify`}
            </CodeBlock>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  Writing a Plugin                                    */}
          {/* ================================================== */}
          <Section id="plugins" title="Writing a Plugin">
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              You can replace any of the 12 layers with your own implementation.
              A plugin is a Python class that matches the expected interface,
              registered via Python entry points.
            </p>

            <h3 className="mb-3 text-lg font-semibold text-warm-800">
              Example: Custom trust plugin
            </h3>
            <p className="mb-3 text-sm text-warm-600">
              Look at the reference implementations in{' '}
              <InlineCode>packages/nest-plugins-reference/</InlineCode> for
              the interface each layer expects. Here&rsquo;s a trust plugin:
            </p>
            <CodeBlock title="my_trust/plugin.py">
{`from nest_core.types import AgentId, Evidence, ReputationScore

class DecayTrust:
    """Custom trust layer with time decay."""

    def __init__(self, identity=None):
        self._scores: dict[AgentId, list[float]] = {}

    async def score(self, agent: AgentId) -> ReputationScore:
        entries = self._scores.get(agent, [])
        if not entries:
            return ReputationScore(
                agent_id=agent, score=0.5,
                confidence=0.0, sample_count=0,
            )
        avg = sum(entries) / len(entries)
        return ReputationScore(
            agent_id=agent, score=avg,
            confidence=min(1.0, len(entries) / 50),
            sample_count=len(entries),
        )

    async def report(self, agent: AgentId, evidence: Evidence):
        val = 1.0 if evidence.kind == "positive" else 0.0
        self._scores.setdefault(agent, []).append(val)`}
            </CodeBlock>

            <h3 className="mb-3 mt-8 text-lg font-semibold text-warm-800">
              Register via entry point
            </h3>
            <CodeBlock title="pyproject.toml">
{`[project]
name = "my-trust-plugin"
version = "0.1.0"
dependencies = ["nest-core"]

[project.entry-points."nest.plugins.trust"]
my_decay = "my_trust.plugin:DecayTrust"`}
            </CodeBlock>

            <p className="mt-4 text-sm text-warm-600">
              Then reference it in your scenario YAML:
            </p>
            <CodeBlock>
{`layers:
  trust: my_decay  # Uses your custom plugin`}
            </CodeBlock>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  CLI Reference                                       */}
          {/* ================================================== */}
          <Section id="cli" title="CLI Reference">
            <p className="mb-6 text-base leading-relaxed text-warm-600">
              All commands are run via <InlineCode>uv run nest</InlineCode> from
              the repo root (or just <InlineCode>nest</InlineCode> if
              installed globally).
            </p>

            <div className="overflow-x-auto rounded-xl border border-warm-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-warm-200 bg-warm-50">
                    <th className="px-4 py-3 text-left font-semibold text-warm-900">
                      Command
                    </th>
                    <th className="px-4 py-3 text-left font-semibold text-warm-900">
                      Description
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-warm-100">
                  {[
                    ['nest run <scenario.yaml>', 'Run a scenario and produce a trace file'],
                    ['nest inspect <trace.jsonl>', 'Print event summary and per-agent stats'],
                    ['nest report <trace.jsonl>', 'Generate an HTML metrics report'],
                    ['nest init <name>', 'Scaffold a new scenario YAML'],
                    ['nest doctor', 'Check installation health and plugin status'],
                    ['nest version', 'Print the installed NEST version'],
                    ['nest plugins list', 'List all installed layer plugins'],
                    ['nest templates list', 'List available agent templates'],
                    ['nest templates show <name>', 'Display a template'],
                    ['nest templates create <name>', 'Create a new agent template'],
                    ['nest templates duplicate <src> <dest>', 'Copy a template'],
                  ].map(([cmd, desc]) => (
                    <tr key={cmd} className="hover:bg-warm-50/50 transition-colors">
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-sm text-crimson">
                        {cmd}
                      </td>
                      <td className="px-4 py-3 text-warm-600">{desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <div className="h-px bg-warm-200" />

          {/* ================================================== */}
          {/*  FAQ                                                 */}
          {/* ================================================== */}
          <Section id="faq" title="FAQ">
            <div className="rounded-xl border border-warm-200 bg-white px-6">
              <FaqItem
                question="Can I pip install this?"
                answer={
                  <p>
                    Not yet. NEST is not published to PyPI. Clone the repo and
                    run <InlineCode>uv sync</InlineCode> to install locally.
                    PyPI publishing is on the roadmap.
                  </p>
                }
              />
              <FaqItem
                question="Do I need an API key?"
                answer={
                  <p>
                    Only for <strong>Tier 2</strong> (LLM-backed) scenarios. Set{' '}
                    <InlineCode>OPENAI_API_KEY</InlineCode> or{' '}
                    <InlineCode>ANTHROPIC_API_KEY</InlineCode>. Tier 1 runs
                    entirely locally with no API calls.
                  </p>
                }
              />
              <FaqItem
                question="How many agents can NEST handle?"
                answer={
                  <p>
                    <strong>Tier 1:</strong> 10,000+ agents on a modern laptop,
                    sub-second runs. <strong>Tier 2:</strong> 10&ndash;100
                    agents, limited by API rate limits and cost.
                  </p>
                }
              />
              <FaqItem
                question="Can I use my own LLM?"
                answer={
                  <p>
                    Yes. Set <InlineCode>llm_provider</InlineCode> and{' '}
                    <InlineCode>llm_model</InlineCode> in your scenario YAML.
                    NEST supports OpenAI, Anthropic, and any OpenAI-compatible
                    endpoint.
                  </p>
                }
              />
              <FaqItem
                question="Is NEST production-ready?"
                answer={
                  <p>
                    No. NEST is research software in active development. It is
                    excellent for experimentation and benchmarking but APIs may
                    change between releases.
                  </p>
                }
              />
              <FaqItem
                question="What does Tier 1 actually test if agents are scripted?"
                answer={
                  <p>
                    Tier 1 tests the <em>protocol</em>, not the agents.
                    It answers: &ldquo;If every agent follows the rules perfectly,
                    does the protocol still work under message drops, network
                    partitions, and Byzantine failures?&rdquo; This is the same
                    logic behind TLA+ model checking&mdash;verify the design
                    before adding implementation complexity.
                  </p>
                }
              />
            </div>
          </Section>

          {/* Footer CTA */}
          <div className="mt-8 rounded-2xl border border-warm-200 bg-warm-50 p-8 text-center sm:p-12">
            <h3 className="text-2xl font-bold tracking-tight text-warm-900">
              Ready to start?
            </h3>
            <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-warm-500">
              Clone the repo and run your first simulation in under two minutes.
            </p>
            <div className="mt-6 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <a
                href="#installation"
                className="inline-flex items-center justify-center rounded-lg bg-crimson px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-crimson-dark"
              >
                Get Started
              </a>
              <a
                href="https://github.com/mariagorskikh/nest"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center rounded-lg border border-warm-300 bg-white px-6 py-2.5 text-sm font-semibold text-warm-700 transition-colors hover:bg-warm-50"
              >
                View on GitHub
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
