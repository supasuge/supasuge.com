

# GrizzHacks8

This year for GrizzHacks8 2026, I was included as part of the *official* organizing team, so I got to help out a lot behind the scenes with some of the general organization of the event + logistics and general decision making. However with that being said, my main task and focus was to create all the challenges  and host/manage and monitor the infrastructure for GrizzHacks8CTF. This year, I made:

- 8 Crypto challenges (*oops*)
- 2 Forensics Challenges
- 2 Rev/Pwn Challenges
- 4 Miscellaneous challenges mainly involving a complex coding tasks or something for fun
- 5 Web challenges involving web exploitation of a previously unknown, though common vulnerability.

## Takeaways

While everything started very smoothly during the event, it didn't take long for sh*t to hit the fan for no apparent reason whatsoever. Here's what happened:

- Change front-end styling through the CTFd dashboard which I have done multiple times before especially during testing leading up to this.
- I added all the challenges + handout/connection details for all of them.
- I realized that once it had his 12pm EST, people still weren't able to access the challenges; so at this point I went back into the CTFd settings/configuration and realized that the time zone was for some reason set to Ukraine time?
- After changing it back to EST, everything worked as it was supposed to. However, the index home page I had made style additions to/edited text from devided to fully self-destruct itself from not just the server but also the running container? Why? I still have absolutely no clue and after hours of reading the source code, I still have no good god damn clue... For this reason, mainly out of frustration; I'll be creating the next best CTF framework for easily configuring/deploying and hosting events, I plan to call it `CTF-ng`.

### What I could've, should've, would've done differently...

- Tested infrastructure more comprehensively
- Edge case handling
- Took into account issues with the GrizzHacks Network itself
- Made sure all correct file versions were uploaded before event began
- Automated the setup/configuration of the menial tasks such as setting up the firewall, users, permissions, installing docker and other sandboxing tools; all that good stuff.