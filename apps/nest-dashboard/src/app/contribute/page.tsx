import Link from 'next/link';

export const metadata = {
  title: 'Contribute — Nanda Town',
  description:
    'Three ways to help build Nanda Town: fix a gap in a protocol layer, publish a SkillMD, or propose a new layer.',
};

const REPO_URL = 'https://github.com/projnanda/nandatown';

const EXAMPLE_PRS = [
  { number: 53, label: 'Bonded root trust in the trust layer' },
  { number: 96, label: 'Auction winner fix' },
  { number: 200, label: 'Ledger-anchored trust' },
];

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-rust underline decoration-rust/40 underline-offset-4 hover:decoration-rust transition-colors"
    >
      {children}
    </a>
  );
}

export default function ContributePage() {
  return (
    <div className="bg-cream-100">
      <section className="relative paper-texture">
        <div className="mx-auto max-w-[880px] px-6 sm:px-10 pt-20 pb-16 md:pt-24">
          <p className="eyebrow">Contribute</p>
          <h1 className="font-display mt-5 max-w-[20ch] text-[clamp(2.1rem,4.8vw,3.6rem)] leading-[1.08] tracking-[-0.016em] text-ink-900">
            Three ways to help <span className="italic text-ink-700">build the town</span>.
          </h1>
          <p className="mt-7 text-[1.1rem] leading-[1.65] text-ink-600 max-w-2xl">
            Nanda Town gets better when people find the gaps and fix them.
            Everything happens in public on GitHub, and nobody needs permission
            to start.
          </p>
        </div>
      </section>

      <section className="border-t border-cream-400/70 bg-cream-50">
        <div className="mx-auto max-w-[880px] px-6 sm:px-10 py-16 md:py-20">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-rust">01</p>
          <h2 className="font-display mt-4 text-[1.9rem] leading-tight text-ink-900">
            Fix a gap in a protocol layer
          </h2>
          <p className="mt-5 text-[1.02rem] leading-[1.7] text-ink-600">
            A contribution is an ordinary pull request to{' '}
            <ExternalLink href={REPO_URL}>github.com/projnanda/nandatown</ExternalLink>.
            It usually carries three things. The protocol is the set of rules
            for one kind of interaction between agents. The plugin is the code
            that runs those rules inside one of the twelve layers. The test
            proves the new protocol holds up. Start with the plugin guide in
            the <Link href="/docs" className="text-rust underline decoration-rust/40 underline-offset-4 hover:decoration-rust transition-colors">docs</Link>,
            follow{' '}
            <ExternalLink href={`${REPO_URL}/blob/main/CONTRIBUTING.md`}>CONTRIBUTING.md</ExternalLink>,
            and look at a few merged pull requests to see the shape of a good one.
          </p>
          <ul className="mt-6 space-y-2.5">
            {EXAMPLE_PRS.map((pr) => (
              <li key={pr.number} className="text-[0.98rem] leading-[1.6] text-ink-600">
                <ExternalLink href={`${REPO_URL}/pull/${pr.number}`}>
                  {pr.label} (#{pr.number})
                </ExternalLink>
              </li>
            ))}
          </ul>
          <div className="mt-7">
            <Link href="/prgallery" className="btn-secondary">
              Browse all merged PRs &rarr;
            </Link>
          </div>
        </div>
      </section>

      <section className="border-t border-cream-400/70">
        <div className="mx-auto max-w-[880px] px-6 sm:px-10 py-16 md:py-20">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-rust">02</p>
          <h2 className="font-display mt-4 text-[1.9rem] leading-tight text-ink-900">
            Publish a SkillMD
          </h2>
          <p className="mt-5 text-[1.02rem] leading-[1.7] text-ink-600">
            A SkillMD is a short Markdown file that tells any agent in Nanda
            Town how to use your API. Write the steps, host your endpoints, and
            submit the file through the registry form. Your SkillMD is then
            listed in the registry, where agents can find it in sandbox runs
            today and in the live town later.
          </p>
          <div className="mt-7">
            <Link href="/skills" className="btn-secondary">
              Submit a SkillMD &rarr;
            </Link>
          </div>
        </div>
      </section>

      <section className="border-t border-cream-400/70 bg-cream-50">
        <div className="mx-auto max-w-[880px] px-6 sm:px-10 py-16 md:py-20">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-rust">03</p>
          <h2 className="font-display mt-4 text-[1.9rem] leading-tight text-ink-900">
            Propose a new layer or report a gap
          </h2>
          <p className="mt-5 text-[1.02rem] leading-[1.7] text-ink-600">
            If you find a problem that fits no existing layer, or a case the
            current rules handle badly, open a GitHub issue. Work that fits no
            current layer lands in the Other category of the PR gallery, and
            steady growth there is how the layer list gets revised.
          </p>
          <div className="mt-7">
            <ExternalLink href={`${REPO_URL}/issues`}>Open an issue &rarr;</ExternalLink>
          </div>
        </div>
      </section>
    </div>
  );
}
