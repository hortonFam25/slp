# Recurring Appointment Feature

## Overview
The recurring appointment feature allows users to create multiple appointments with configurable frequency patterns, similar to Outlook or Gmail scheduling.

## Components

### RecurringSchedule Component
**Location**: `./RecurringSchedule.tsx`

A reusable component that provides:
- **Frequency Options**: Weekly or Monthly scheduling
- **Interval Selection**: Every X weeks/months (1-12 weeks, 1-6 months)
- **Day of Week Selection**: For weekly - choose multiple days; For monthly - same day pattern
- **End Conditions**: Stop after X appointments or on a specific date
- **Preview**: Shows the first 5 upcoming appointment dates

#### Props
```typescript
interface RecurringScheduleProps {
  value: RecurringConfig;
  onChange: (config: RecurringConfig) => void;
  startDate: Date;
  disabled?: boolean;
  maxOccurrences?: number;
  maxEndDate?: Date;
}
```

#### RecurringConfig Interface
```typescript
interface RecurringConfig {
  isRecurring: boolean;
  frequency: 'weekly' | 'monthly';
  interval: number; // Every X weeks/months
  daysOfWeek: number[]; // 0 = Sunday, 1 = Monday, etc.
  endType: 'date' | 'occurrences';
  endDate?: Date;
  maxOccurrences?: number;
}
```

### Utility Functions

#### generateRecurringDates()
Generates an array of all appointment dates based on the recurring configuration.

```typescript
function generateRecurringDates(
  startDate: Date,
  config: RecurringConfig
): Date[]
```

## Integration

### Student Scheduling Modal
The `StudentSchedulingModal` now includes the recurring appointment functionality:

1. **Recurring Schedule Section**: Shows after Goals selection
2. **Smart Defaults**: When enabled, defaults to weekly on the same day
3. **Form Validation**: Ensures required fields are filled before enabling recurring options
4. **Conflict Handling**: Each recurring appointment is validated separately

### Backend Handling
The backend creates individual appointments for each recurring date:
- Each appointment is validated for conflicts independently
- Appointments include a note indicating their position in the series (e.g., "Recurring 3/10")
- All goal/objective planning is preserved for each appointment

## Usage Examples

### Weekly Recurring Appointment
- Every Tuesday and Thursday for 8 weeks
- Student: John Doe
- Time: 10:00 AM - 10:30 AM
- Goals: Same goals for all sessions

### Monthly Recurring Appointment  
- Every 2nd Friday of the month for 6 months
- Student: Jane Smith
- Time: 2:00 PM - 3:00 PM
- Objectives: Specific objectives planned

## Future Enhancements

### Time Block Integration
The `RecurringSchedule` component is designed to be reusable and can be easily integrated into time block creation modals when they are implemented.

### Bulk Operations
Potential future features:
- Bulk edit recurring appointments
- Bulk cancel/reschedule series
- Exception handling (skip specific dates)

## Technical Notes

### Date Handling
- Uses local timezone for all date calculations
- Preserves time-of-day across different dates
- Handles month boundaries and leap years correctly

### Performance
- Frontend generates all dates client-side
- Backend creates appointments individually for proper validation
- Each appointment is a separate database record

### Error Handling
- Individual appointment failures don't affect the entire series
- Conflict detection per appointment
- User feedback for partial failures

## Best Practices

1. **Validation**: Always validate recurring config before generating dates
2. **User Feedback**: Show preview of upcoming appointments
3. **Conflict Management**: Handle conflicts gracefully with clear messaging
4. **Performance**: Limit maximum occurrences to prevent performance issues
5. **Accessibility**: Ensure all controls are properly labeled and keyboard accessible
