# Application composition Future Updates

- Preserve separate primary/advisory model settings when adding configuration controls; avoid reconnecting Flow through a callback that repeats an already completed inference.

- Keep provider configuration injectable; introduce startup lifecycle hooks only when a concrete module needs them.
