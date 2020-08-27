====
Peek
====

.. image:: https://github.com/ywangd/peek/workflows/Peek/badge.svg
        :target: https://github.com/ywangd/peek

Peek is an interactive CLI tool for working with Elasticsearch clusters.
It is like `Kibana Console <https://www.elastic.co/guide/en/kibana/current/console-kibana.html>`_
running in terminal with additional features for tinkers.


Installation
------------

Please note the project requires Python 3.6+. It is currently under development and is recommended to install
it in development mode from the source repository for easier update.

1. Clone the `repository <https://github.com/ywangd/peek>`_
2. Inside the project root directory, run ``pip install -e .``

Alternatively, it can be installed from PyPI with ``pip install es-peek``.

The tool is now available as the ``peek`` command. Other than HTTP calls to Elasticsearch clusters, type ``help``
to get a list of builtin functions.

* To enable auto-completions for APIs (WIP), run ``make get-specs`` to pull API specs from the
  `Kibana project <https://github.com/elastic/kibana>`_.
* Run tests with ``tox -s true``

Features
--------

Peek supports most editing features offered by Kibana Console, e.g. syntax highlighting, auto-formatting, auto-indent,
auto-completion (WIP), par-editing, triple-quotes, etc. It also offers following additional features:

* Lightweight CLI tool
* Multiplex a single terminal session to multiple Elasticsearch clusters or multiple credentials to a single cluster
* Connect to `Elastic Cloud <https://cloud.elastic.co/>`_ with Cloud ID
* Multiple authentication schemes in a single terminal, including UserPass, API key, Token, SAML, OIDC, Kerberos, PKI
* Support run-as, x-opaque-id, and arbitrary request headers
* More flexible quotes and comma for the JSON payload
* Load JSON payload from external file
* Run file input in batch mode
* History management
* Capture terminal input and output into file
* Shell out
* Minimal scripting support
* Extensible via external scripts

Sample Usages
-------------

Assuming a locally running Elasticsearch cluster, the following sample can be directly copy/paste and executed in
a Peek session:

.. code-block:: javascript

  // Basic API call
  GET /_cluster/health

  // Index a single document
  POST /my-index/_doc
  {'foo': "bar"}

  // Bulk indexing
  // Press <F3> to switch between pretty and compact formatting for the JSON payload
  PUT _bulk
  {"index":{"_index":"test","_id":"1"}}
  {"field1":"value1"}

  // Shell out to download the EQL threat hunting demo file
  !curl -o normalized-T1117-AtomicRed-regsvr32.json https://raw.githubusercontent.com/elastic/elasticsearch/master/docs/src/test/resources/normalized-T1117-AtomicRed-regsvr32.json

  // Bulk indexing the above downloaded file
  POST my-index-000001/_bulk
  @normalized-T1117-AtomicRed-regsvr32.json

  // Execute an EQL query
  GET /my-index-000001/_eql/search?filter_path=-hits.events
  {
    "query": """
      any where process.name == "regsvr32.exe"
    """,
    "size": 200
  }

  // Create an API key
  PUT _security/api_key
  {
    "name": "key-1",  // extra comma is acceptable
  }

  // Connect using the above generated API key
  // The dot notation is used to index into JSON object and array
  connect api_key=_.@id + ":" + _.@api_key  // default host is localhost:9200

  // Can also connect to Elastic Cloud with Cloud ID
  connect cloud_id='YOUR_CLOUD_ID' username='elastic'

  // List available connections
  session
  session @info  // check details
  session rename='my-cloud-cluster'  // give a friendly name to the current connection
  session remove=0  // remove the first connection (zero-based index)

  // Builtin help
  help  // list available functions
  help session  // a bit more detailed info about the "session" builtin function

  // Capture the terminal I/O
  capture @start
  capture  // show capture status

  // Run-AS etc
  GET _security/_authenticate runas='foo' xoid='my-x-opaque-id' headers={'some-other-header': 'blah'}

  // If the cluster has SAML integration configured, authenticate with saml
  // Note this opens a web browser to perform the front-channel flow
  saml_authenticate

  // Load and run an external script
  run 'my-setup.es'

  // Stop the capture
  capture @stop

  // Check configuration location and values
  config

  // Minimal scripting for populating an index
  let tags = range(0, 100)
  for i in tags {
    PUT ("my-index/_doc/" + i)
    { 'tag': i, "value": i * i }
  }

The tool can also run in batch mode. Assuming above commands are saved in a file called ``script.es``,
it can be executed as:

.. code-block:: bash

  # Positional argument
  peek script.es

  # Pipe
  cat script.es | peek

  # Or with heredoc
  peek << EOF
  GET /_cluster/health
  // etc
  EOF

External scripts can used to provide extra functions. They are simple Python scripts that define
and expose callabes under a variable named ``EXPORTS``. Please refer `natives.py <peek/natives.py>`_
for examples.

Credits
-------

