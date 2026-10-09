Simple Django application to learn and making something useful for myself and friends. Translated only to polish (language of friend group)
Idea is to allow login without any account, only to claim named profile. In case of repetition, user will receive suggestion to claim similar name, or to log as this user if that your profile. 
To avoid unauthorized access every sub page has password gate, set up during creation. This way we have basic uniques of passwords, and base protection to not overcomplicate things for friends with
low technical abilities or shorter memory span.

Currently hub has two kind of modules:
# Gift List
Simple gift list page to claim gifts from prepared list, created via django admin panel

# Events
To simplify event organization, it allows users to claim things they will prepare/bring for event. Split items into categories - some users may want to claim whole category of things with one click, without clicking on each separate item
As with gift list, list is submitted via django admin panel

Built on Python on Django with gunicorn. Basic unit and e2e tests in pytest and playwright 
