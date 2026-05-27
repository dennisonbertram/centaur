---
title: What is Centaur?
description: Centaur is the open-source control plane for shared AI agents, durable workflows, isolated sandboxes, approved tools, and credential-safe automation.
---

<main className="what-page">
  <section className="what-hero" aria-labelledby="what-title">
    <p className="what-kicker">Control plane for production agents</p>
    <h1 id="what-title">Centaur gives team agents an operating model.</h1>
    <p className="what-lede">Centaur is the open-source control plane for shared AI agents that need to run inside real infrastructure: Slack threads, durable workflow runs, Kubernetes sandboxes, approved tools, replayable events, and outbound calls that never expose raw long-lived secrets to the agent workspace.</p>
    <div className="what-actions" aria-label="Primary links">
      <a href="/quickstart">Start locally</a>
      <a href="/architecture">Read architecture</a>
    </div>
  </section>

  <aside className="what-credit" aria-label="Project credit">
    <span>Built and open-sourced by</span>
    <div className="what-credit-logos">
      <a href="https://paradigm.xyz" aria-label="Paradigm">
        <img src="/paradigm-logo.svg" alt="Paradigm" />
      </a>
      <a className="what-credit-tempo" href="https://tempo.xyz" aria-label="Tempo">
        <img src="/tempo-logo.svg" alt="Tempo" />
      </a>
    </div>
  </aside>

  <section className="what-map" aria-label="Centaur system map">
    <a href="#durable-agent-turns">
      <span>01</span>
      <strong>Durable turns</strong>
      <small>Every request, stream event, result, and final delivery obligation is recorded.</small>
    </a>
    <a href="#isolated-sandboxes">
      <span>02</span>
      <strong>Sandboxed runtimes</strong>
      <small>One warm Kubernetes runtime per thread, fenced by assignment generation.</small>
    </a>
    <a href="#approved-tools">
      <span>03</span>
      <strong>Approved tools</strong>
      <small>Agents call typed tools through Centaur instead of carrying local credentials.</small>
    </a>
    <a href="#durable-workflows">
      <span>04</span>
      <strong>Workflows</strong>
      <small>Python handlers checkpoint, sleep, wait for events, and call agents.</small>
    </a>
  </section>

  <section className="what-section" id="durable-agent-turns">
    <div className="what-section-head">
      <p className="what-kicker">Durable execution</p>
      <h2>Agent turns survive disconnects, restarts, and slow delivery.</h2>
    </div>
    <div className="what-copy">
      <p>Centaur stores the user turn, runtime assignment, execution request, streamed events, terminal state, and final delivery state in Postgres. A Slack client can disconnect, an API worker can restart, and a consumer can reconnect with the last event it saw.</p>
      <p>The client protocol stays small: spawn or reuse a runtime, persist a message, enqueue execution, then stream or replay durable events. Slack, internal dashboards, and API clients all use the same control-plane path.</p>
    </div>
  </section>

  <ol className="what-flow" aria-label="Durable client protocol">
    <li>
      <span>spawn</span>
      <p>Pin a warm runtime to a thread and receive the current assignment generation.</p>
    </li>
    <li>
      <span>message</span>
      <p>Persist the user turn and extract inline attachment bytes into durable storage.</p>
    </li>
    <li>
      <span>execute</span>
      <p>Create the execution row and final-delivery obligation; workers drive the sandbox.</p>
    </li>
    <li>
      <span>events</span>
      <p>Stream or replay raw harness events, projected events, and terminal state.</p>
    </li>
  </ol>

  <section className="what-section" id="isolated-sandboxes">
    <div className="what-section-head">
      <p className="what-kicker">Runtime isolation</p>
      <h2>Every conversation runs in a managed sandbox.</h2>
    </div>
    <div className="what-copy">
      <p>Centaur assigns each thread to a Kubernetes sandbox pod running the selected harness, such as Amp, Claude Code, Codex, or another CLI adapter. The API owns runtime assignment, execution serialization, cancellation, recovery, and release.</p>
      <p>Sandboxes speak a stable Anthropic-style message format with the API. Harness-specific quirks stay inside the sandbox adapter, so product surfaces do not need to know how each CLI handles text, images, files, interrupts, or output events.</p>
    </div>
  </section>

  <figure className="architecture-figure what-architecture">
    <img src="/brand/containers.svg" alt="Centaur deployment layout: the open-source kernel wrapped by an organization overlay and a per-app repository." />
    <figcaption>Centaur separates the open-source kernel, organization overlay, and application repo. Teams can keep the core generic while layering their own prompts, tools, workflows, personas, and product integrations.</figcaption>
  </figure>

  <section className="what-grid" aria-label="Centaur building blocks">
    <article className="what-card" id="approved-tools">
      <p className="what-kicker">Capabilities</p>
      <h2>Approved tools</h2>
      <p>Tool plugins expose typed REST methods through Centaur's API. Agents call those tools over the control plane instead of using ad hoc local secrets or one-off scripts.</p>
      <a href="/extend/tools">Create a tool</a>
    </article>
    <article className="what-card">
      <p className="what-kicker">Secrets</p>
      <h2>Credential-safe egress</h2>
      <p>Sandboxes receive placeholders. Real credentials live behind the proxy layer and are injected only for configured hosts and headers.</p>
      <a href="/security#credentials">Review the model</a>
    </article>
    <article className="what-card" id="durable-workflows">
      <p className="what-kicker">Orchestration</p>
      <h2>Durable workflows</h2>
      <p>Workflow handlers checkpoint steps, sleep, wait for external events, start child workflows, and run agent turns as part of larger automation.</p>
      <a href="/extend/workflows">Write a workflow</a>
    </article>
    <article className="what-card">
      <p className="what-kicker">Surfaces</p>
      <h2>Thin clients</h2>
      <p>Slackbot and external clients persist input, call the API, and render output. Execution, replay, sandboxing, and final delivery stay in Centaur.</p>
      <a href="/architecture#service-interface-contracts">See contracts</a>
    </article>
  </section>

  <section className="what-section what-section-tight">
    <div className="what-section-head">
      <p className="what-kicker">When to use it</p>
      <h2>Centaur is for agents that are becoming production workflows.</h2>
    </div>
    <div className="what-copy">
      <p>Use Centaur when agents must be shared, recoverable, auditable, and able to call real systems. If a demo script is enough, Centaur is probably too much. If Slack threads, internal workflows, and product integrations are starting to depend on agents, Centaur gives them a durable operating model.</p>
      <ul className="what-checklist">
        <li>Multiple people need the same agent runtime and tool surface.</li>
        <li>Outputs must be replayable after disconnects or worker restarts.</li>
        <li>Credentials need to stay outside the agent workspace.</li>
        <li>Teams need overlays for organization-specific prompts and workflows.</li>
      </ul>
    </div>
  </section>

  <footer className="what-footer">
    <a href="/quickstart">Run the quickstart</a>
    <a href="/deploying-in-production">Deploy in production</a>
    <a href="https://github.com/paradigmxyz/centaur">View on GitHub</a>
  </footer>
</main>
