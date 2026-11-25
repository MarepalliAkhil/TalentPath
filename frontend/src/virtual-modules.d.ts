declare module 'virtual:repo-facts' {
  import type { RepoFacts } from '../build/repoFacts';

  const facts: RepoFacts;
  export default facts;
}

/** wss:// origin of the Render backend, derived from vercel.json at build time ('' until deployed). */
declare const __RENDER_WS_ORIGIN__: string;
