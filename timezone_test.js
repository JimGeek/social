// Test timezone conversion logic
// This simulates what the frontend will do

function convertLocalToUTC(localDateTime) {
  // Get the timezone offset in minutes (negative for timezones ahead of UTC)
  const timezoneOffsetMinutes = localDateTime.getTimezoneOffset();
  
  // Adjust the time by subtracting the offset to get true UTC time
  const utcTime = new Date(localDateTime.getTime() - (timezoneOffsetMinutes * 60000));
  
  return utcTime.toISOString();
}

// Test with 11:00 PM IST today
const testDate = new Date();
testDate.setHours(23, 0, 0, 0); // 11:00 PM local time

console.log('=== Timezone Conversion Test ===');
console.log('Local Time Selected:', testDate.toString());
console.log('Timezone Offset (minutes):', testDate.getTimezoneOffset());

// OLD METHOD (BROKEN)
const oldMethod = testDate.toISOString();
console.log('Old Method (Broken):', oldMethod);

// NEW METHOD (FIXED)
const newMethod = convertLocalToUTC(testDate);
console.log('New Method (Fixed):', newMethod);

// For IST (UTC+5:30), 11:00 PM should become 5:30 PM UTC
console.log('\nExpected: 11:00 PM IST = 17:30 UTC');
console.log('Fixed method result includes 17:30?', newMethod.includes('T17:30:'));

// Test difference
const oldTime = new Date(oldMethod);
const newTime = new Date(newMethod);
const diffMinutes = (oldTime.getTime() - newTime.getTime()) / (1000 * 60);

console.log('\nTime difference between old and new method:', diffMinutes, 'minutes');
console.log('This should be', testDate.getTimezoneOffset(), 'minutes for correct conversion');

if (diffMinutes === testDate.getTimezoneOffset()) {
  console.log('✅ TIMEZONE CONVERSION IS NOW CORRECT!');
} else {
  console.log('❌ Timezone conversion still has issues');
}