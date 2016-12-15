Server
###############################

.. contents::

.. highlight:: sh


Launch a server with API
=========================

The API
--------------

You can launch server with API::

  server = Server(path)
  if server.is_running():
      print('Server is already running')
      exit(0)
  is_ok = server.check_consistency(quick=True)
  if not is_ok:
      print('Database is not consistent')
      exit(0)
  server.start(detach=False, loop=False)
  print('Launch reindexation')
  reindex_success = server.reindex_catalog()
  if reindex_success:
      print('Reindex was successfull')
  else:
      print('Error in reindexation')
  retour = server.do_request('GET', '/')
  print(retour)
  server.stop()
