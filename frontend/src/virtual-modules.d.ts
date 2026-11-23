declare module 'virtual:repo-facts' {
  import type { RepoFacts } from '../build/repoFacts';

  const facts: RepoFacts;
  export default facts;
}
