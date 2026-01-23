=======
History
=======

0.5.0 (unreleased)
------------------

* Bump the default auto-completion version from Elasticsearch 8.2 to 9.2
* Allow configuring the Elasticsearch specification version with `autocompletion_version` in peekrc
* Drop legacy Kibana autocompletion support
* Drop Python 3.8 and 3.9 support
* Support Python 3.11 to 3.14

0.4.0 (2024-01-25)
------------------

* Upgrade the dependency for elasticsearch client library from 7.17 to 8.12. It now depends on the low level transport library instead of the high level client library. (#200)
* Hatch as the project management tool (#205)
* Pipe output to external command (#203)
* New commands to download extension file (#207), show context variables
* Show request duration in output header (#182)
* Fix smart connection for changing password (#196)
* Load pre-defined variables (#211)
* Better support for ad-hoc output file (#204)
* Support path_prefix for proxy'd elasticsearch instances (#206)
* Other misc fixes and improvements

0.3.1 (2023-01-23)
------------------

* Fix a bug for autocompletion on role name with leading underscore
* Fix a bug where query parameter value can be non-string
* Fix bug in instanceOf completion of candidate properties
* Fix crash on missing type

0.3.0 (2022-04-10)
------------------

* All dependencies upgraded to latest version (except elasticsearch-py gets pinned to 7.17.x)
* Minimal Python version required is now 3.8 (it may work with 3.7 as well, but not tested)
* Change auto-completion to use the new Elasticsearch Specification
* Capture file is now runnable
* Other misc improvements

0.2.2 (2021-02-28)
------------------

* Allow start with no connection (also allow to remove the last connection)
* Display warning headers from server
* Support the HEAD http method
* Smart date math expression handling
* Support post-event callback for both session and connection
* Display now takes formatted text for style and color

0.2.1 (2020-09-22)
------------------

* Fix distribution packaging

0.2.0 (2020-09-20)
------------------

* Auto-completion is fully functional
* Various improvements


0.1.1 (2020-08-29)
------------------

* Support persisting session across restart of the CLI


0.1.0 (2020-07-22)
------------------

* First commit
