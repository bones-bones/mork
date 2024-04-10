- Fix token links
- ~~Add people to drive folder~~
- ~~finish owl~~
- documentation/readme
- ~~secret enhancement~~
- not secret enhancements
- tag people when errata is needed
- replace google client with gspread
- stormstorm images are borked
- Database Bot Readable see if this can be deleted
- The regular reddit posting is code is gross. fix it




```
aceback (most recent call last):
  File "/home/-/.local/lib/python3.11/site-packages/discord/ext/commands/core.py", line 235, in wrapped
    ret = await coro(*args, **kwargs)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/-/mork/cogs/Lifecycle.py", line 237, in compileveto
    await acceptCard(
  File "/home/-/mork/acceptCard.py", line 47, in acceptCard
    allCardNames = cardSheetUnapproved.col_values(1)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/-/.local/lib/python3.11/site-packages/gspread/worksheet.py", line 712, in col_values
    data = self.client.values_get(
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/-/.local/lib/python3.11/site-packages/gspread/http_client.py", line 231, in values_get
    r = self.request("get", url, params=params)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/-/.local/lib/python3.11/site-packages/gspread/http_client.py", line 123, in request
    raise APIError(response)
gspread.exceptions.APIError: {'code': 500, 'message': 'Internal error encountered.', 'status': 'INTERNAL'}

The above exception was the direct cause of the following exception:
```