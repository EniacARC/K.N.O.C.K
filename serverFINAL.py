"""
sip server:
need to use thread pool that is PER MSG
no need for registration for invite - needs validation if not registered
pools communicate through CALLS - this is the way thread pools have context

for every response - send to the other side. maybe send something back to the sender
everytime you return - if sdp then change ports and save for the rtp call


register - register and add to endpoints, meaning people that you can CALL TO.
registered users are allowed to be contacted, and don't need extra validation

cleanup thread that closes inactive calls, expired reg
(maybe make reg persistent)

for requests - need auth.
for response no need for auth

AUTH:
you send auth challenge. the uac send a NEW request back with auth (including all params needed to calculate).
the server saves ha1 not plaintext.

I have a call class
"""