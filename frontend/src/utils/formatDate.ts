import { format, formatDistanceToNow } from 'date-fns';

export function formatTimestamp(isoString: string): string {
  return format(new Date(isoString), 'HH:mm');
}

export function formatFullDate(isoString: string): string {
  return format(new Date(isoString), 'yyyy-MM-dd HH:mm:ss');
}

export function formatRelative(isoString: string): string {
  return formatDistanceToNow(new Date(isoString), { addSuffix: true });
}
