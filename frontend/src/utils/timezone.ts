/**
 * Timezone utility functions for proper date/time handling
 */

/**
 * Converts a local datetime to UTC properly
 * @param localDateTime - Date object in local timezone
 * @returns ISO string in UTC
 */
export const convertLocalToUTC = (localDateTime: Date): string => {
  // Get the timezone offset in minutes (negative for timezones ahead of UTC)
  const timezoneOffsetMinutes = localDateTime.getTimezoneOffset();
  
  // Adjust the time by subtracting the offset to get true UTC time
  const utcTime = new Date(localDateTime.getTime() - (timezoneOffsetMinutes * 60000));
  
  return utcTime.toISOString();
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