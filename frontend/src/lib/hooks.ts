import { useEffect, useState } from 'react';
import { brand } from './brand';

export function useMediaQuery(query: string): boolean {
  const get = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);
  return matches;
}

export function useDocumentTitle(title: string | undefined, full = false): void {
  useEffect(() => {
    if (!title) return;
    document.title = full ? title : `${title} | ${brand.name}`;
  }, [title, full]);
}

function setMeta(selector: string, create: () => HTMLElement, apply: (el: HTMLElement) => void) {
  let el = document.head.querySelector<HTMLElement>(selector);
  if (!el) {
    el = create();
    document.head.appendChild(el);
  }
  apply(el);
  return el;
}

/** Title, meta description, canonical link and JSON-LD for public pages. */
export function useSeo(seo: { title: string; description: string; canonical?: string; jsonLd?: object } | null) {
  useEffect(() => {
    if (!seo) return;
    document.title = seo.title;
    setMeta(
      'meta[name="description"]',
      () => Object.assign(document.createElement('meta'), { name: 'description' }),
      (el) => el.setAttribute('content', seo.description),
    );
    const added: HTMLElement[] = [];
    if (seo.canonical) {
      added.push(
        setMeta(
          'link[rel="canonical"]',
          () => Object.assign(document.createElement('link'), { rel: 'canonical' }),
          (el) => el.setAttribute('href', seo.canonical ?? ''),
        ),
      );
    }
    if (seo.jsonLd) {
      const script = document.createElement('script');
      script.type = 'application/ld+json';
      script.id = 'jobposting-ld';
      script.textContent = JSON.stringify(seo.jsonLd);
      document.head.querySelector('#jobposting-ld')?.remove();
      document.head.appendChild(script);
      added.push(script);
    }
    return () => added.forEach((el) => el.remove());
  }, [seo]);
}

export function useNoIndex(): void {
  useEffect(() => {
    const meta = Object.assign(document.createElement('meta'), { name: 'robots', content: 'noindex' });
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);
}
