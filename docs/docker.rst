Docker
###############################

.. highlight:: sh

You can access ikaaro in docker here: https://hub.docker.com/r/hforge/ikaaro/

Pull ikaaro image::

  $ docker pull hforge/ikaaro

Launch ikaaro image::

  $ docker run -it --rm hforge/ikaaro /bin/sh

Create a Dockerfile base on ikaaro image::

  $ vim Dockerfile

  FROM hforge/ikaaro:latest
  WORKDIR /home/ikaaro
  # Install your packages & dependencies
  RUN git clone git@github.com:xxx/xxx.git
  RUN pip install -r requirements.txt
  RUN pip install -r requirements-dev.txt
  RUN pip install -r requirements-test.txt

