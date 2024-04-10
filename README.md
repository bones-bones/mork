I have no idea what is going on, I think Exalted and Cirion built this. (and Zaxer too?)



# Setting up for local development
1. Install VSCode and Python plugin
1. Get Python >=3.9
1. Install dependencies via `pip install -r requirements.txt`
1. Make a copy of `discord_token.template.py` called `discord_token.py`. Add the bot token.
1. Make a copy of `reddit_secrets.template.py` called `reddit_secrets.py`. Add creds. https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki 
1. Get a copy of `client_secrets.json`, put it in secrets
1. `python Mork.py`
1. Oh uh if stuff isn't working try python3



# starting the bot from scratch
1. Make a new Discord application and invite it to the server
1. The bot will need OAuth2 scopes of `bot` and `applications.commands`
1. Bot permissions will need read/write messages, read message history, and send messages.
1. Ask someone to add the both to the server and give it the bot role too


# To get it to work
- to get a copy to work you'd have to do a few things
- Make a new Discord application on the dev portal and invite it to the server. Replace the token in the code with the new token.
- Make a Google Service Account and invite it to the Hellscube Database spreadsheet. Put its credentials somewhere so they can loaded.
- Do the authentication part https://pythonhosted.org/PyDrive/quickstart.html so that the quote and gamenight commands work. Also change the file ids.



# Troubleshooting
## None of your dependencies are showing up
It's pretty easy to get multiple versions of Python installed. particularly 3? If you have this issue, run pip in the context of the python version you want: `python3 -m pip install -r requirements.txt`


# Concepts
- Uh go read about discord cogs, just write your feature-specific code in one of those, then reference it in Mork.
- If Mork needs to track that it has interacted with a post outside of the submissions channel, it usually uses `await message.add_reaction(hc_constants.ACCEPT)`. It would be super nice to unify that.




# Assorted commands
`nohup python3 Mork.py >/dev/null 2>&1`
`nohup python3 -u Mork.py > nohup.out` - for looking at logs
`rm -rf mork && unzip mork.zip && cd mork && ps -ef | grep python`


`nohup python3 -u Mork.py > nohup.out`



# The lifecycle of a card

## 1. Coming up with ideas
Uh just do it

## 1.a What makes a good card
Don't ask me, seriously.

## 2. Brainstorming
Once you have your concept, you'll want to head over to the two brainstorming channels: draw-three and put-two-back. Here you can collect feedback and/or inspire others. (if you have a dogshit idea that you just need to get out of your head, go to the brazil channel)

## 2.a Art
While the definition of what art is is fraught at best, try to avoid AI art. If you have the concept, but don't have the skills yet, try the #art-request channel

## 3. Submitting
One you have your finished card and are ready to throw it into the lion pit, head over to #submissions. Create a post that consists of the name of your card and the picture. Nothing more, nothing less. Make sure you do it right, because you can only post once an hour. Once posted, Mork will delete your post, and repost it as a poll. Polls with have thumbs up, thumbs down, and X. The X is there in case you decide you need that post to be removed.

And now you wait. If your card has 25 more upvotes than downvotes after 24 hours, but within 7 days. It makes it to the next round! When the conditions are met, Mork will delete the post and announce it in #submissions-discussion.

## 4. Veto time
Right after Mork sends the message in #submissions-discussion, it'll create a thread in a secret channel accessed only by the Veto Council. Mork attaches the relevant voting emoji and tags the Veto Council. They will discuss and assess the card and after some amount of time (when the council has decided on a handful of cards) it will meet one of its fates

## 4.1 It passes!
Cong!
rats!

Your card will go down in infamy. By that, I mean it gets posted to reddit with the Accepted flair, added to the unapproved database sheet (Copie van Database), and posted to card-list.

## 4.2 It needs errata!
The good news is, the card has a good concept. The bad news is that it needs balancing. Once you've been made aware, you can reach out in #errata-discussion for input, tweak your card, then submit it to #errata-submissions. From there, a Veto Council member will post it to the secret channel, and Mork will create a new thread and votes there. Rinse and repeat.

## 4.3 Vetoed!
For some reason, the card was vetoed. This can be for all kinds of reasons: difficult to tweak, doesn't fit with the themes, or ????. ???? is really the worst one.

## 4.4 Veto Hell
Essentially purgatory. A decision wasn't reached one way or another in time... but don't give up yet! Maybe it'll be in the next round.

## 4.5 ????
There's always the chance a process fails. Who knows what happens then.

## 5. It percolates out
From time to time, a mod will take the entries in the unapproved sheet of the database, and transcribe them to the main sheet. Once the cards are in the main sheet, they'll start to show up in other places. Mork will search against them, hellfall will list them, cube XML files will be created that include them, and cube cobra will show them too. (The exact timings on when these will happen is fuzzy at best.)
