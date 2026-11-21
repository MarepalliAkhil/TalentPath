import { describe, expect, it } from 'vitest';
import { assistant, brand } from './brand';

describe('brand config', () => {
  it('keeps product identity in one file', () => {
    expect(brand.name).toBeTruthy();
    expect(brand.tagline).toBeTruthy();
    Object.values(brand.colors).forEach((hex) => expect(hex).toMatch(/^#[0-9A-F]{6}$/i));
  });

  it('holds the HIRA assistant name and display string', () => {
    expect(assistant.name).toBe('HIRA');
    expect(assistant.fullName).toBe('Hiring Intelligence & Recruiting Assistant');
    expect(assistant.display).toBe('HIRA · Hiring Intelligence & Recruiting Assistant');
  });
});
