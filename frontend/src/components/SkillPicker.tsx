import { useId, useState, type KeyboardEvent } from 'react';
import type { Skill } from '@/lib/types';
import { Icon } from './Icon';

/** Choose skills from the taxonomy. Typing a synonym ("JS") finds the canonical skill. */
export function SkillPicker({
  label,
  skills,
  value,
  onChange,
  error,
  exclude = [],
}: {
  label: string;
  skills: Skill[];
  value: string[];
  onChange: (ids: string[]) => void;
  error?: string;
  exclude?: string[];
}) {
  const id = useId();
  const [text, setText] = useState('');
  const [notice, setNotice] = useState('');
  const byId = new Map(skills.map((s) => [s.id, s]));

  const find = (term: string) => {
    const t = term.trim().toLowerCase();
    return skills.find((s) => s.name.toLowerCase() === t || s.slug === t || s.synonyms.some((syn) => syn.toLowerCase() === t));
  };

  const add = () => {
    const skill = find(text);
    if (!skill) {
      setNotice(text.trim() ? `“${text.trim()}” is not in the skills list.` : '');
      return;
    }
    if (exclude.includes(skill.id)) {
      setNotice(`${skill.name} is already in the other list.`);
      return;
    }
    if (!value.includes(skill.id)) onChange([...value, skill.id]);
    setNotice(`${skill.name} added.`);
    setText('');
  };

  const onKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      add();
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-ink">
        {label}
      </label>
      <div className="flex gap-2">
        <input
          id={id}
          list={`${id}-list`}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          aria-describedby={`${id}-help${error ? ` ${id}-error` : ''}`}
          aria-invalid={error ? true : undefined}
          className="w-full rounded-xl border border-ink/15 bg-white/90 px-3 py-2.5 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
          placeholder="Type a skill, e.g. Python or JS"
        />
        <button type="button" onClick={add} className="min-h-11 rounded-xl bg-ink px-4 text-sm font-semibold text-white">
          Add<span className="sr-only"> to {label}</span>
        </button>
      </div>
      <datalist id={`${id}-list`}>
        {skills.map((s) => (
          <option key={s.id} value={s.name} />
        ))}
      </datalist>
      <p id={`${id}-help`} className="text-xs text-muted" aria-live="polite">
        {notice || 'Press Enter to add.'}
      </p>
      {error && (
        <p id={`${id}-error`} className="text-sm font-medium text-danger">
          {error}
        </p>
      )}
      <ul className="flex flex-wrap gap-1.5" aria-label={`${label} selected`}>
        {value.map((skillId) => {
          const skill = byId.get(skillId);
          if (!skill) return null;
          return (
            <li
              key={skillId}
              className="inline-flex items-center gap-1 rounded-full bg-primary-soft py-1 pl-3 pr-1 text-sm font-medium text-primary-strong"
            >
              {skill.name}
              <button
                type="button"
                onClick={() => onChange(value.filter((v) => v !== skillId))}
                className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-white/70"
                aria-label={`Remove ${skill.name}`}
              >
                <Icon name="close" className="h-3.5 w-3.5" />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
