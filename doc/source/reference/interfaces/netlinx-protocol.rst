Netlinx Protocol
================

Connection Parameters
---------------------

.. list-table::
    :widths: auto

    * - Protocol
      - TCP
    * - Netlinx server port
      - ``1234``
    * - Line delimiter
      - ``b'\n'`` (or ``0x0A``)


Message Format
--------------

Each message should begin with ``<`` and end with ``>``::

    '<TALLY.PGM:1=0>'

All characters outside of the opening and closing brackets are to be ignored
by both the client and the server.


Message Parameters
------------------

.. list-table::
    :widths: auto
    :header-rows: 1

    * - Identifier
      - Name
      - Type
      - Description
    * - n
      - Integer
      - Item index
      - The item index (zero-based)
    * - v
      - Value
      - Integer
      - The item value. If boolean, 0 = off, 1 = on
    * - t
      - Time
      - Integer
      - Duration in milliseconds

Command / Query Messages
------------------------

.. list-table::
    :widths: auto
    :header-rows: 1

    * - Request
      - Response
      - Description
    * - PING?
      - PONG
      - Check communication status
    * - TALLY.PGM?
      - TALLY.PGM:n=v
      - Request all program tally status.

        Responses are separated by line breaks.
    * - TALLY.PVW?
      - TALLY.PVW:n=v
      - Request all preview tally status.

        Responses are separated by line breaks.
    * - TALLY.PGM:n?
      - TALLY.PGM:n=v
      - Request a single program tally status
    * - UPDATE.TIME=t
      - UPDATE.TIME=t
      - Set timeout for update messages
    * - UPDATE.UNSOLICITED=v
      - UPDATE.UNSOLICITED=v
      - Turn unsolicited updates on or off



Status Update Messages
----------------------

.. list-table::
    :widths: auto
    :header-rows: 1

    * - Message
      - Description
    * - TALLY.PGM:n=v
      - Sent on changes for program tally.

        Automatically sent if unsolicited updates are on.
    * - TALLY.PVW:n=v
      - Sent on changes for program tally.

        Automatically sent if unsolicited updates are on.
