(****************************************************************************)
(*                                                                          *)
(* This file is part of JVConnected.                                        *)
(*                                                                          *)
(* JVConnected is free software: you can redistribute it and/or modify      *)
(* it under the terms of the GNU General Public License as published by     *)
(* the Free Software Foundation, either version 3 of the License, or        *)
(* (at your option) any later version.                                      *)
(*                                                                          *)
(* JVConnected is distributed in the hope that it will be useful,           *)
(* but WITHOUT ANY WARRANTY; without even the implied warranty of           *)
(* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            *)
(* GNU General Public License for more details.                             *)
(*                                                                          *)
(* You should have received a copy of the GNU General Public License        *)
(* along with JVConnected.  If not, see <https://www.gnu.org/licenses/>.    *)
(*                                                                          *)
(****************************************************************************)

MODULE_NAME='JVConnected-Server' (DEV dvServerIP,
                                  DEV vdvCtrl,
                                  DEV vdvTally,
                                  INTEGER nDebugFlag)


DEFINE_CONSTANT

    RX_BUFFERSIZE = 4096
    MAX_TALLY = 32

DEFINE_VARIABLE

    //CONSTANT    CHAR    cMessageStart[] = "'<'"
    //CONSTANT    CHAR    cMessageStop[]  = "'>'"

    VOLATILE    INTEGER nServerPort = 0
    VOLATILE    INTEGER nServerOnline
    VOLATILE    INTEGER nClientConnected
    VOLATILE    INTEGER nRX
    VOLATILE    CHAR    cIPBuffer[RX_BUFFERSIZE]

    VOLATILE    INTEGER nSendUnsolicited = 1
    VOLATILE    INTEGER nPgmTally[MAX_TALLY]
    VOLATILE    INTEGER nPvwTally[MAX_TALLY]

    VOLATILE    LONG lTLSendUpdateTimes[] = {30000}
    VOLATILE    LONG lTLSendUpdateID = 1


DEFINE_FUNCTION SLONG SERVER_OPEN ()
{
    STACK_VAR SLONG slResult
    IF (!nServerOnline)
    {
        slResult = IP_SERVER_OPEN (dvServerIP.Port,nServerPort,IP_TCP)
        IF (slResult=0) nServerOnline = 1
    }
}

DEFINE_FUNCTION SLONG SERVER_CLOSE ()
{
    IP_SERVER_CLOSE (dvServerIP.Port)
    nServerOnline = 0
}

DEFINE_FUNCTION CHAR[600] HEXSTR (clStr[])
{
    STACK_VAR CHAR clHexStr[600]
    STACK_VAR INTEGER nlLoop
    clHexStr = ''
    FOR (nlLoop=1;nlLoop<=LENGTH_STRING(clStr);nlLoop++)
        clHexStr = "clHexStr,'$',ITOHEX(clStr[nlLoop]),' '"
    RETURN clHexStr
}

DEFINE_FUNCTION DEBUG (CHAR clStr[])
{
    IF (nDebugFlag) SEND_STRING 0,clStr
}

DEFINE_FUNCTION SEND_TO_CLIENT(CHAR clMessage[])
{
    IF (nClientConnected) {
        DEBUG("'SEND TO CLIENT: ','<', clMessage, '>'")
        SEND_STRING dvServerIP, "'<', clMessage, '>',10"
    }
}

DEFINE_FUNCTION SEND_TALLY(INTEGER nlTallyTypeIsPvw, INTEGER nlIdx)
{
    STACK_VAR INTEGER nlValue
    STACK_VAR CHAR clTallyType[3]
    IF (nlTallyTypeIsPvw) {
        nlValue = nPvwTally[nlIdx]
        nlValue = [vdvTally,nlIdx+MAX_TALLY]=1
        clTallyType = 'PVW'
    } ELSE {
        nlValue = nPgmTally[nlIdx]
        /* nlValue = [vdvTally,nlIdx]=1 */
        clTallyType = 'PGM'
    }
    SEND_TO_CLIENT("'TALLY.', clTallyType, ':', ITOA(nlIdx-1), '=', ITOA(nlValue)")
}

DEFINE_FUNCTION SEND_ALL_TALLY(INTEGER nlTallyTypeIsPvw)
{
    STACK_VAR INTEGER nlLoop
    FOR (nlLoop=1;nlLoop<=MAX_TALLY;nlLoop++)
        SEND_TALLY(nlTallyTypeIsPvw, nlLoop)
}

DEFINE_FUNCTION SET_UPDATE_TIMEOUT(LONG llTimeoutMilli)
{
    IF (TIMELINE_ACTIVE(lTLSendUpdateID))
        TIMELINE_KILL(lTLSendUpdateID)
    IF (llTimeoutMilli > 0) {
        lTLSendUpdateTimes[0] = llTimeoutMilli
        TIMELINE_CREATE(lTLSendUpdateID, lTLSendUpdateTimes, 1, TIMELINE_RELATIVE, TIMELINE_REPEAT)
    }
}

DEFINE_FUNCTION SET_UNSOLICITED(INTEGER nlValue)
{
    nSendUnsolicited = nlValue
}

DEFINE_EVENT

    DATA_EVENT [vdvCtrl]
    {
        ONLINE:
        {
            IF (!TIMELINE_ACTIVE(lTLSendUpdateID))
                TIMELINE_CREATE(lTLSendUpdateID, lTLSendUpdateTimes, 1, TIMELINE_RELATIVE, TIMELINE_REPEAT)
        }
        COMMAND:
        {
            STACK_VAR CHAR clParseMain[100]
            STACK_VAR CHAR clParseJunk[100]
            clParseMain = DATA.TEXT
            SELECT
            {
                ACTIVE (FIND_STRING(clParseMain,'PORT=',1)):
                {
                    clParseJunk = REMOVE_STRING(clParseMain,'PORT=',1)
                    nServerPort = ATOI(clParseMain)
                }
            }
        }
    }

    DATA_EVENT [dvServerIP]
    {
        ONLINE:
        {
            nClientConnected = 1
            DEBUG ('IPSERVER CLIENT CONNECTED')
        }
        STRING:
        {
            STACK_VAR CHAR clParseMain[RX_BUFFERSIZE]
            STACK_VAR CHAR clParseJunk[RX_BUFFERSIZE]
            STACK_VAR INTEGER nlTallyTypeIsPvw
            STACK_VAR INTEGER nlIdx
            STACK_VAR LONG llTimeoutMilli

            cIPBuffer = "cIPBuffer,DATA.TEXT"
            DEBUG("'FROM CLIENT: ', DATA.TEXT")
            CANCEL_WAIT 'RX'
            nRX = 1
            WAIT 5 'RX'
            {
                nRX = 0
            }
            WHILE (FIND_STRING(cIPBuffer, '>', 1)) {
                clParseMain = REMOVE_STRING(cIPBuffer, '>', 1)
                IF (FIND_STRING(clParseMain, '<', 1)) {
                    SELECT {
                        ACTIVE (FIND_STRING(clParseMain, 'PING', 1)): {
                            SEND_TO_CLIENT('PONG')
                        }
                        ACTIVE (FIND_STRING(clParseMain, 'TALLY.', 1)): {
                            clParseJunk = REMOVE_STRING(clParseMain, 'TALLY.', 1)
                            SELECT {
                                ACTIVE (FIND_STRING(clParseMain, 'PGM', 1)): {
                                    nlTallyTypeIsPvw = 0
                                    clParseJunk = REMOVE_STRING(clParseMain, 'PGM', 1)
                                }
                                ACTIVE (FIND_STRING(clParseMain, 'PVW', 1)): {
                                    nlTallyTypeIsPvw = 1
                                    clParseJunk = REMOVE_STRING(clParseMain, 'PVW', 1)
                                }
                                ACTIVE (1): {
                                    nlTallyTypeIsPvw = 255
                                }
                            }
                            IF (nlTallyTypeIsPvw != 255){
                                SELECT {
                                    ACTIVE (FIND_STRING(clParseMain, ':', 1)): {
                                        clParseJunk = REMOVE_STRING(clParseMain, ':', 1)
                                        /* clParseJunk = REMOVE_STRING(clParseMain, '?', 1) */
                                        nlIdx = ATOI(clParseMain)
                                        SEND_TALLY(nlTallyTypeIsPvw, nlIdx+1)
                                    }
                                    ACTIVE (1): {
                                        SEND_ALL_TALLY(nlTallyTypeIsPvw)
                                    }
                                }
                            }
                        }
                        ACTIVE (FIND_STRING(clParseMain, 'UPDATE.', 1)): {
                            clParseJunk = REMOVE_STRING(clParseMain, 'UPDATE.', 1)
                            SELECT {
                                ACTIVE (FIND_STRING(clParseMain, 'TIME=', 1)): {
                                    clParseJunk = REMOVE_STRING(clParseMain, 'TIME=', 1)
                                    llTimeoutMilli = ATOL(clParseMain)
                                    SET_UPDATE_TIMEOUT(llTimeoutMilli)
                                }
                                ACTIVE (FIND_STRING(clParseMain, 'UNSOLICITED=', 1)): {
                                    clParseJunk = REMOVE_STRING(clParseMain, 'UNSOLICITED=', 1)
                                    nlIdx = ATOI(clParseMain)
                                    SET_UNSOLICITED(nlIdx)
                                }
                            }
                        }
                    }
                }
            }
            /* WHILE (FIND_STRING(cIPBuffer,cSysexStop,1))
            {
                clParseMain = REMOVE_STRING(cIPBuffer,cSysexStop,1)
                IF (FIND_STRING(clParseMain,cSysexStart,1))
                {
                    //clParseJunk = REMOVE_STRING(clParseMain,cSysexStart,1)
                    SEND_STRING vdvPassThru,clParseMain
                    DEBUG ("'FROM IPSERVER CLIENT: ',HEXSTR(clParseMain)")
                }
            } */
            IF (!FIND_STRING(cIPBuffer,'<',1) && !FIND_STRING(cIPBuffer,'>',1))
                cIPBuffer = ''
        }
        OFFLINE:
        {
            nClientConnected = 0
            cIPBuffer = ''
            DEBUG ('IPSERVER CLIENT DISCONNECTED')
            SERVER_CLOSE()
        }
        ONERROR:
        {
            DEBUG ("'IPSERVER ERRROR: ',ITOA(DATA.NUMBER)")
	    SERVER_CLOSE()
        }
    }

    CHANNEL_EVENT [vdvTally, 0]
    {
        ON: {
            STACK_VAR INTEGER nlIdx
	    nlIdx = CHANNEL.CHANNEL
            IF (nlIdx<=MAX_TALLY){
                nPgmTally[nlIdx] = 1
                IF (nSendUnsolicited)
                    SEND_TALLY(0, nlIdx)
            } ELSE {
                nlIdx = nlIdx - MAX_TALLY
                IF (nlIdx<=MAX_TALLY){
                    nPvwTally[nlIdx] = 1
                    IF (nSendUnsolicited)
                        SEND_TALLY(1, nlIdx)
                }
            }
        }
        OFF: {
            STACK_VAR INTEGER nlIdx
	    nlIdx = CHANNEL.CHANNEL
            IF (nlIdx<=MAX_TALLY){
                nPgmTally[nlIdx] = 0
                IF (nSendUnsolicited)
                    SEND_TALLY(0, nlIdx)
            } ELSE {
                nlIdx = nlIdx - MAX_TALLY
                IF (nlIdx<=MAX_TALLY){
                    nPvwTally[nlIdx] = 0
                    IF (nSendUnsolicited)
                        SEND_TALLY(1, nlIdx)
                }
            }
        }
    }

    TIMELINE_EVENT [lTLSendUpdateID]
    {
        SEND_ALL_TALLY(0)
        SEND_ALL_TALLY(1)
    }

DEFINE_PROGRAM

    WAIT 11
    {
        IF (!nServerOnline && nServerPort > 0)
        {
            SERVER_OPEN ()
        }
    }
