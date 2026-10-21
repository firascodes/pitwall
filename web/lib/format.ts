export const usd = (n: number) => `$${n < 0.01 ? n.toFixed(6) : n.toFixed(4)}`;

export const short = (name: string) => name.split(" ").at(-1) ?? name;

/** Leclerc -> LEC, the way timing screens name drivers. */
export const code = (name: string) => short(name).slice(0, 3).toUpperCase();

export const plural = (n: number, word: string) =>
  `${n} ${n === 1 ? word : word.endsWith("y") ? `${word.slice(0, -1)}ies` : `${word}s`}`;

export function seconds(ms: number) {
  return `${(ms / 1000).toFixed(1)}s`;
}
