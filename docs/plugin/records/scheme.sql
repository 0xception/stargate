--
-- Database scheme for asterisk stargate integration.
--

-- ------------------------------------------------------------------

--
-- Database: `stargate`
--
-- CREATE DATABASE stargate;
-- USE stargate;

--
-- Table structure for call records
--

CREATE TABLE IF NOT EXISTS `records` (
    `id` int(32) NOT NULL auto_increment,
    `uid` varchar(32) NOT NULL default '',
    `channel` varchar(80) NOT NULL default '',
    `caller_number` varchar(80) NOT NULL default '',
    `caller_name` varchar(80) NOT NULL default '',
    `caller_dnid` varchar(80) NOT NULL default '',
    `account_code` varchar(32) NOT NULL default '',
    `status` varchar(32) NOT NULL default '',
    `agent` int(11),
    `ticket` int(11),
    `call_start` datetime NOT NULL default '0000-00-00 00:00:00',
    `call_end` datetime NOT NULL default '0000-00-00 00:00:00',
    `hold_start` datetime NOT NULL default '0000-00-00 00:00:00',
    `hold_end` datetime NOT NULL default '0000-00-00 00:00:00',
    `talk_start` datetime NOT NULL default '0000-00-00 00:00:00',
    `talk_end` datetime NOT NULL default '0000-00-00 00:00:00',
    PRIMARY KEY (`id`),
    UNIQUE KEY `Unique ID` (`uid`),
    KEY `Caller Number` (`caller_number`),
    KEY `Caller DNID` (`caller_dnid`),
    KEY `Account Code` (`account_code`)
    KEY `Agent ID` (`agent`)
    KEY `Support Ticket Number` (`ticket`)
) ENGINE=InnoDB  DEFAULT CHARSET=latin1;
