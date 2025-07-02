# Config Flow Improvements

## Overview
The configuration flow has been significantly simplified to provide a better user experience with sensible defaults while still allowing advanced customization for power users.

## Key Improvements

### 1. Simplified Initial Setup
- **Before**: Users had to go through multiple required steps even if they wanted defaults
- **After**: 
  - Step 1: Select state and service type
  - Step 2: Option to use all defaults or configure advanced settings
  - Can complete setup in just 2 steps!

### 2. Progressive Disclosure
- Basic users can complete setup quickly with sensible defaults:
  - Residential rate plan
  - Weekly PDF updates
  - Cost sensors enabled
  - 30 kWh average daily usage
  
- Advanced users can still access all options:
  - Different rate plans (TOU, EV, Commercial)
  - PDF update frequency
  - TOU schedule customization
  - Custom holidays
  - Summer month definitions

### 3. Skip Options at Each Step
- **Rate Plan Step**: Added "Configure Additional Options" checkbox
  - Unchecking skips directly to completion with defaults
- **TOU Config Step**: Added "Skip Additional Options" checkbox
  - Allows quick TOU setup without diving into consumption settings
- **Additional Options**: All fields are optional with good defaults

### 4. Improved Options Flow
- **Simplified Main View**: Shows only the most important options:
  - Rate schedule
  - Consumption entity selection
  - Average daily usage
  - Enable/disable cost sensors
  
- **Advanced Options**: Available through "Show Advanced Options" checkbox:
  - Update frequency
  - Summer months
  - Additional charges
  - TOU time configuration

### 5. Better Consumption Entity Detection
- Now scans all sensor entities, not just those in the registry
- Looks for any sensor with kWh or Wh units
- Provides friendly names in dropdown
- "Manual Entry" option clearly labeled

## User Flow Examples

### Quick Setup (2 steps)
1. Select state: Colorado, Service: Electric → Next
2. "Configure Advanced Options": No → Done!

### Basic Customization (3-4 steps)
1. Select state and service → Next
2. Configure Advanced: Yes → Next
3. Select rate plan, Configure More: No → Done!

### Full Customization
1. Select state and service → Next
2. Configure Advanced: Yes → Next
3. Select rate plan and options → Next
4. Configure TOU settings (if applicable) → Next
5. Configure consumption and other options → Done!

## Benefits
- **Reduced Friction**: New users can get started in seconds
- **Flexibility**: Power users still have full control
- **Clear Defaults**: All defaults are sensible and clearly shown
- **Progressive Complexity**: Advanced options only shown when needed
- **Better UX**: Each step has clear purpose and skip options