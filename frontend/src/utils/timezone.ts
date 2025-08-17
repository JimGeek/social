/**
 * Timezone utility functions for proper date/time handling
 */

/**
 * Converts a local datetime to UTC properly
 * @param localDateTime - Date object in local timezone
 * @returns ISO string in UTC
 */
export const convertLocalToUTC = (localDateTime: Date): string => {
  // Actually, toISOString() already does the correct conversion!
  // When you create a Date object from datetime-local input,
  // it's already in local timezone and toISOString() converts it properly to UTC
  return localDateTime.toISOString();
};

/**
 * Converts a UTC datetime string to local time
 * @param utcDateTimeString - ISO string in UTC
 * @returns Date object in local timezone
 */
export const convertUTCToLocal = (utcDateTimeString: string): Date => {
  return new Date(utcDateTimeString);
};

/**
 * Gets the current timezone information
 */
export const getTimezoneInfo = () => {
  const now = new Date();
  const offsetMinutes = now.getTimezoneOffset();
  const offsetHours = Math.abs(offsetMinutes) / 60;
  const offsetSign = offsetMinutes <= 0 ? '+' : '-';
  
  return {
    offsetMinutes,
    offsetHours,
    offsetString: `UTC${offsetSign}${offsetHours}`,
    timezoneName: Intl.DateTimeFormat().resolvedOptions().timeZone
  };
};

/**
 * Formats a date for debugging timezone issues
 */
export const debugTimezone = (date: Date, label: string = '') => {
  const info = getTimezoneInfo();
  console.log(`[Timezone Debug${label ? ' - ' + label : ''}]:`, {
    localTime: date.toString(),
    utcTime: date.toUTCString(),
    isoString: date.toISOString(),
    convertedUTC: convertLocalToUTC(date),
    timezoneInfo: info
  });
};