import { describe, expect, it } from 'vitest';
import { safeNext } from './redirect';

describe('sign-in redirect', () => {
  it('keeps same-site paths', () => {
    expect(safeNext('/leave/approvals?tab=mine')).toBe('/leave/approvals?tab=mine');
    expect(safeNext(null)).toBeNull();
  });

  it('refuses other sites, including the backslash and control-character tricks', () => {
    for (const bad of ['https://evil.example', '//evil.example', '/\\evil.example', '/\\/evil.example', '/\t/evil.example', 'leave']) {
      expect(safeNext(bad), bad).toBeNull();
    }
  });
});
