<script lang="ts" module>
  // 24×24 stroke icons (currentColor).
  const PATHS = {
    play: 'M7 4.5v15l12-7.5z',
    stop: 'M6.5 6.5h11v11h-11z',
    plus: 'M12 5v14M5 12h14',
    minus: 'M5 12h14',
    x: 'M6 6l12 12M18 6L6 18',
    check: 'M5 12.5l4.5 4.5L19 7.5',
    edit: 'M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4',
    trash: 'M4 7h16M9 7V4.5h6V7M6.5 7l1 13h9l1-13M10 11v6M14 11v6',
    'chevron-left': 'M15 5l-7 7 7 7',
    'chevron-right': 'M9 5l7 7-7 7',
    'chevron-down': 'M5 9l7 7 7-7',
    'chevron-up': 'M5 15l7-7 7 7',
    calendar: 'M4 6.5h16v14H4zM4 10.5h16M8 3.5v5M16 3.5v5',
    clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3.5 2',
    timer: 'M12 21a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM12 9v4l2.5 1.5M9.5 2.5h5M19 5.5l1.5 1.5',
    list: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
    chart: 'M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-8M20 16v-3',
    settings:
      'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
    undo: 'M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11',
    download: 'M12 4v11M7 10.5l5 5 5-5M5 20h14',
    upload: 'M12 20V9M7 13.5l5-5 5 5M5 4h14',
    image: 'M4 5h16v14H4zM4 16l5-5 4 4 2.5-2.5L20 17M15.5 9.5h.01',
    file: 'M14 3H6v18h12V7zM14 3v4h4',
    info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v5M12 8h.01',
    question: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17h.01',
    warning: 'M12 3.5L2.5 20h19zM12 10v4.5M12 17.5h.01',
    error: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9 9l6 6M15 9l-6 6',
    success: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 12.5l2.7 2.7L16 10',
    sun: 'M12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9zM12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
    moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z',
    monitor: 'M3 4.5h18v12H3zM8 20.5h8M12 16.5v4',
    flame: 'M12 21c-3.9 0-6.5-2.7-6.5-6.3 0-4 3.3-5.9 4-10.2 2.2 1.4 3.4 3.4 3.5 5.4 1-.6 1.6-1.6 1.8-2.8 2.2 1.9 3.7 4.7 3.7 7.6 0 3.6-2.6 6.3-6.5 6.3z',
    refresh: 'M20 11a8 8 0 0 0-14.7-4.3L4 8.5M4 4v4.5h4.5M4 13a8 8 0 0 0 14.7 4.3l1.3-1.8M20 20v-4.5h-4.5',
    external: 'M14 4h6v6M20 4l-9 9M18 14v6H4V6h6',
    more: 'M5 12h.01M12 12h.01M19 12h.01',
    search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4',
    euro: 'M17.5 6.5A7 7 0 1 0 17.5 17.5M4 10h9M4 14h9',
    sparkles: 'M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM19 15l.8 2.2 2.2.8-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z',
    trophy: 'M8 4h8v5a4 4 0 0 1-8 0zM8 6H5v1.5A3 3 0 0 0 8 10.5M16 6h3v1.5a3 3 0 0 1-3 3M12 13v4M8.5 20h7M10 17h4',
    puzzle: 'M10 4a2 2 0 1 1 4 0v2h4v4h-2a2 2 0 1 0 0 4h2v4h-4v-2a2 2 0 1 0-4 0v2H6v-4h2a2 2 0 1 0 0-4H6V6h4z',
    keyboard: 'M3 6h18v12H3zM7 10h.01M11 10h.01M15 10h.01M7 14h10',
  } as const;
  export type IconName = keyof typeof PATHS;
  export const ICON_NAMES = Object.keys(PATHS) as IconName[];
</script>

<script lang="ts">
  let {
    name,
    size = 18,
    stroke = 2,
    label,
    class: cls = '',
  }: { name: IconName; size?: number | string; stroke?: number; label?: string; class?: string } = $props();

  const filled = $derived(name === 'play' || name === 'stop');
</script>

<svg
  class="icon {cls}"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill={filled ? 'currentColor' : 'none'}
  stroke="currentColor"
  stroke-width={stroke}
  stroke-linecap="round"
  stroke-linejoin="round"
  role={label ? 'img' : undefined}
  aria-label={label}
  aria-hidden={label ? undefined : 'true'}
>
  <path d={PATHS[name]} />
</svg>

<style>
  .icon {
    flex: none;
    display: inline-block;
    vertical-align: middle;
  }
</style>
