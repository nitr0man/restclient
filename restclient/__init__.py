#!/usr/bin/python

# Copyright (c) 2007
# Columbia Center For New Media Teaching And Learning (CCNMTL)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the CCNMTL nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY CCNMTL ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <copyright holder> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


"""
REST client convenience library

This module contains everything that's needed for a nice, simple REST client.

the main function it provides is rest_invoke(), which will make an HTTP
request to a REST server. it allows for all kinds of nice things like:

    * alternative verbs: POST, PUT, DELETE, etc.
    * parameters
    * file uploads (multipart/form-data)
    * proper unicode handling
    * Accept: headers
    * ability to specify other headers

this library is mostly a wrapper around the standard urllib and
httplib2 functionality, but also includes file upload support via a
python cookbook recipe
(http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/146306) and
has had additional work to make sure high unicode characters in the
parameters or headers don't cause any UnicodeEncodeError problems.

Joe Gregario's httplib2 library is required. It can be easy_installed,
or downloaded nose is required to run the unit tests.

CHANGESET:
  * 2012-11-17 - Anders - flake8 cleanup, version bump
  * 2012-11-16 - hickey - added support for sending JSON data
  * 2012-11-16 - hickey - added debuglevel to httplib_params
  * 2012-04-16 - alexmock - added httplib_params for fine-grained control of
                            httplib2
  * 2010-10-11 - Anders - added 'credentials' parameter to support HTTP Auth
  * 2010-07-25 - Anders - merged Greg Baker's <gregb@ifost.org.au> patch for
                          https urls
  * 2007-06-13 - Anders - added experimental, partial support for HTTPCallback
  * 2007-03-28 - Anders - merged Christopher Hesse's patches for fix_params and
                          to eliminate mutable default args
  * 2007-03-14 - Anders - quieted BaseHTTPServer in the test suite
  * 2007-03-06 - Anders - merged Christopher Hesse's bugfix and self-contained
                          test suite
  * 2006-12-01 - Anders - switched to httplib2. Improved handling of parameters
                          and made it stricter about unicode in headers
                          (only ASCII is allowed). Added resp option. More
                          docstrings.
  * 2006-03-23 - Anders - working around cherrypy bug properly now by being
                          more careful about sending the right
  * 2006-03-17 - Anders - fixed my broken refactoring :) also added async
                          support and we now use post_multipart for everything
                          since it works around a cherrypy bug.
  * 2006-03-10 - Anders - refactored and added GET, POST, PUT, and DELETE
                          convenience functions
  * 2006-02-22 - Anders - handles ints in params + headers correctly now

"""

import httplib2
import mimetypes
import threading
import types
import urllib
try:
    import json
except ImportError:
    import simplejson as json


__version__ = "0.11.0"


def post_multipart(host, selector, method, fields, files, headers=None,
                   return_resp=False, scheme="http", credentials=None,
                   httplib_params=None):
    """
    Post fields and files to an http host as multipart/form-data.
    fields is a sequence of (name, value) elements for regular form
    fields.  files is a sequence of (name, filename, value) elements
    for data to be uploaded as files Return the server's response
    page.
    """
    if headers is None:
        headers = {}
    if httplib_params is None:
        httplib_params = {}
    content_type, body = encode_multipart_formdata(fields, files)

    # Check for debuglevel in httplib_params
    orig_debuglevel = httplib2.debuglevel
    if 'debuglevel' in httplib_params:
        httplib2.debuglevel = httplib_params['debuglevel']
        del httplib_params['debuglevel']
    h = httplib2.Http(**httplib_params)
    if credentials:
        h.add_credentials(*credentials)
    headers['Content-Length'] = str(len(body))
    headers['Content-Type'] = content_type
    resp, content = h.request("%s://%s%s" % (scheme, host, selector),
                              method, body, headers)
    # reset httplib2 debuglevel to original value
    httplib2.debuglevel = orig_debuglevel
    # if the content-type is JSON, then convert back to objects.
    if resp['content-type'].startswith('application/json'):
        content = json.loads(content)
    elif method == 'GET' and content.startswith('{') and content.endswith('}'):
        content = json.loads(content)
    elif method == 'GET' and content.startswith('[') and content.endswith(']'):
        content = json.loads(content)
    if return_resp:
        return resp, content
    else:
        return content


def encode_multipart_formdata(fields, files):
    """
    fields is a sequence of (name, value) elements for regular form
    fields.  files is a sequence of (name, filename, value) elements
    for data to be uploaded as files Return (content_type, body) ready
    for httplib.HTTP instance
    """
    BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = '\r\n'
    L = []
    for (key, value) in fields:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"' % key)
        L.append('')
        L.append(str(value))
    for (key, filename, value) in files:
        L.append('--' + BOUNDARY)
        L.append('Content-Disposition: form-data; name="%s"; filename="%s"'
                 % (key, filename))
        L.append('Content-Type: %s' % get_content_type(filename))
        L.append('')
        L.append(str(value))
    L.append('--' + BOUNDARY + '--')
    L.append('')
    L = [str(l) for l in L]

    body = CRLF.join(L)
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    return content_type, body


def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'


def GET(url, params=None, files=None, accept=[], headers=None, do_async=False,
        resp=False, credentials=None, httplib_params=None):
    """ make an HTTP GET request.

    performs a GET request to the specified URL and returns the body
    of the response.

    in addition, parameters and headers can be specified (as dicts). a
    list of mimetypes to accept may be specified.

    if do_async=True is passed in, it will perform the request in a new
    thread and immediately return nothing.

    if resp=True is passed in, it will return a tuple of an httplib2
    response object and the content instead of just the content.
    """
    return rest_invoke(url=url, method=u"GET", params=params,
                       files=files, accept=accept, headers=headers,
                       do_async=do_async, resp=resp, credentials=credentials,
                       httplib_params=httplib_params)


def POST(url, params=None, files=None, accept=[], headers=None,
         do_async=True, resp=False, credentials=None, httplib_params=None):
    """ make an HTTP POST request.

    performs a POST request to the specified URL.

    in addition, parameters and headers can be specified (as dicts). a
    list of mimetypes to accept may be specified.

    files to upload may be specified. the data structure for them is:

       param : {'file' : file object, 'filename' : filename}

    and immediately return nothing.

    by default POST() performs the request in a new thread and returns
    (nothing) immediately.

    To wait for the response and have it return the body of the
    response, specify do_async=False.

    if resp=True is passed in, it will return a tuple of an httplib2
    response object and the content instead of just the content.
    """
    return rest_invoke(url=url, method=u"POST", params=params,
                       files=files, accept=accept, headers=headers,
                       do_async=do_async, resp=resp, credentials=credentials,
                       httplib_params=httplib_params)


def PUT(url, params=None, files=None, accept=[], headers=None,
        do_async=True, resp=False, credentials=None, httplib_params=None):
    """ make an HTTP PUT request.

    performs a PUT request to the specified URL.

    in addition, parameters and headers can be specified (as dicts). a
    list of mimetypes to accept may be specified.

    files to upload may be specified. the data structure for them is:

       param : {'file' : file object, 'filename' : filename}

    and immediately return nothing.

    by default PUT() performs the request in a new thread and returns
    (nothing) immediately.

    To wait for the response and have it return the body of the
    response, specify do_async=False.

    if resp=True is passed in, it will return a tuple of an httplib2
    response object and the content instead of just the content.
    """

    return rest_invoke(url=url, method=u"PUT", params=params,
                       files=files, accept=accept, headers=headers,
                       do_async=do_async, resp=resp, credentials=credentials,
                       httplib_params=httplib_params)


def DELETE(url, params=None, files=None, accept=[], headers=None,
           do_async=True, resp=False, credentials=None,
           httplib_params=None):
    """ make an HTTP DELETE request.

    performs a DELETE request to the specified URL.

    in addition, parameters and headers can be specified (as dicts). a
    list of mimetypes to accept may be specified.

    by default DELETE() performs the request in a new thread and
    returns (nothing) immediately.

    To wait for the response and have it return the body of the
    response, specify do_async=False.

    if resp=True is passed in, it will return a tuple of an httplib2
    response object and the content instead of just the content.
    """

    return rest_invoke(url=url, method=u"DELETE", params=params,
                       files=files, accept=accept, headers=headers,
                       do_async=do_async, resp=resp, credentials=credentials,
                       httplib_params=httplib_params)


def rest_invoke(url, method=u"GET", params=None, files=None,
                accept=[], headers=None, do_async=False, resp=False,
                httpcallback=None, credentials=None,
                httplib_params=None):
    """ make an HTTP request with all the trimmings.

    rest_invoke() will make an HTTP request and can handle all the
    advanced things that are necessary for a proper REST client to handle:

    * alternative verbs: POST, PUT, DELETE, etc.
    * parameters
    * file uploads (multipart/form-data)
    * proper unicode handling
    * Accept: headers
    * ability to specify other headers

    rest_invoke() returns the body of the response that it gets from
    the server.

    rest_invoke() does not try to do any fancy error handling. if the
    server is down or gives an error, it will propagate up to the
    caller.

    this function expects to receive unicode strings. passing in byte
    strings risks double encoding.

    parameters:

    url: the full url you are making the request to
    method: HTTP verb to use. defaults to GET
    params: dictionary of params to include in the request
    files: dictionary of files to upload. the structure is

          param : {'file' : file object, 'filename' : filename}

    accept: list of mimetypes to accept in order of
            preference. defaults to '*/*'
    headers: dictionary of additional headers to send to the server
    do_async: Boolean. if true, does request in new thread and nothing is
           returned
    resp: Boolean. if true, returns a tuple of response,
          content. otherwise returns just content
    httpcallback: None. an HTTPCallback object (see
                  http://microapps.org/HTTP_Callback). If specified,
                  it will override the other params.
    httplib_params: dict of parameters supplied to httplib2 - for
                    example ca_certs='/etc/ssl/certs/ca-certificates.crt'
    """
    if do_async:
        threading.Thread(target=_rest_invoke,
                         args=(url, method, params, files, accept,
                               headers, resp, httpcallback, credentials,
                               httplib_params))
    else:
        return _rest_invoke(url, method, params, files, accept, headers,
                            resp, httpcallback, credentials, httplib_params)


def _rest_invoke(url, method=u"GET", params=None, files=None, accept=None,
                 headers=None, resp=False, httpcallback=None,
                 credentials=None, httplib_params=None):
    if params is None:
        params = {}
    if files is None:
        files = {}
    if accept is None:
        accept = []
    if headers is None:
        headers = {}

    if httpcallback is not None:
        method = httpcallback.method
        url = httpcallback.url
        if httpcallback.queryString != "":
            if "?" not in url:
                url += "?" + httpcallback.queryString
            else:
                url += "&" * httpcallback.queryString
        ps = httpcallback.params
        for (k, v) in ps:
            params[k] = v
        hs = httpcallback.headers
        for (k, v) in hs:
            headers[k] = v

        if httpcallback.username or httpcallback.password:
            print("warning: restclient can't handle HTTP auth yet")
        if httpcallback.redirections != 5:
            print("warning: restclient doesn't support "
                  "HTTPCallback's restrictions yet")
        if httpcallback.follow_all_redirects:
            print("warning: restclient doesn't support "
                  "HTTPCallback's follow_all_redirects_yet")
        if httpcallback.body != "":
            print("warning: restclient doesn't support HTTPCallback's body yet")

    headers = add_accepts(accept, headers)
    if method in ['POST', 'PUT'] and 'Content-Type' not in headers:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        params = urllib.parse.urlencode(fix_params(params))
    elif (method in ['POST', 'PUT'] and
          headers['Content-Type'] == 'application/json'):
        params = json.dumps(params)
    else:
        # GET and DELETE requests
        params = urllib.parse.urlencode(fix_params(params))

    if files:
        return post_multipart(extract_host(url), extract_path(url),
                              method,
                              unpack_params(params),
                              unpack_files(fix_files(files)),
                              fix_headers(headers),
                              resp, scheme=extract_scheme(url),
                              credentials=credentials,
                              httplib_params=httplib_params)
    else:
        return non_multipart(params, extract_host(url),
                             method, extract_path(url),
                             fix_headers(headers), resp,
                             scheme=extract_scheme(url),
                             credentials=credentials,
                             httplib_params=httplib_params)


def non_multipart(params, host, method, path, headers, return_resp,
                  scheme="http", credentials=None, httplib_params=None):
    if httplib_params is None:
        httplib_params = {}
    if method == "GET":
        headers['Content-Length'] = '0'
        if params:
            # put the params into the url instead of the body
            if "?" not in path:
                path += "?" + params
            else:
                if path.endswith('?'):
                    path += params
                else:
                    path += "&" + params
            params = ""
    else:
        headers['Content-Length'] = str(len(params))

    # Check for debuglevel in httplib_params
    orig_debuglevel = httplib2.debuglevel
    if 'debuglevel' in httplib_params:
        httplib2.debuglevel = httplib_params['debuglevel']
        del httplib_params['debuglevel']
    h = httplib2.Http(**httplib_params)
    if credentials:
        h.add_credentials(*credentials)
    url = "%s://%s%s" % (scheme, host, path)
    resp, content = h.request(url, method,
                              params, headers)
    # reset httplib2 debuglevel to original value
    httplib2.debuglevel = orig_debuglevel
    # if the content-type is JSON, then convert back to objects.
    if resp['content-type'].startswith('application/json'):
        content = json.loads(content)
    elif method == 'GET' and content.startswith(b'{') and content.endswith(b'}'):
        content = json.loads(content)
    elif method == 'GET' and content.startswith(b'[') and content.endswith(b']'):
        content = json.loads(content)
    if return_resp:
        return resp, content
    else:
        return content


def extract_host(url):
    return my_urlparse(url)[1]


def extract_scheme(url):
    return my_urlparse(url)[0]


def extract_path(url):
    return my_urlparse(url)[2]


def my_urlparse(url):
    (scheme, host, path, ps, query, fragment) = urllib.parse.urlparse(url)
    if ps:
        path += ";" + ps
    if query:
        path += "?" + query

    return (scheme, host, path)


def unpack_params(params):
    return [(k, params[k]) for k in params.keys()]


def unpack_files(files):
    return [(k, files[k]['filename'], files[k]['file']) for k in files.keys()]


def add_accepts(accept=None, headers=None):
    if accept is None:
        accept = []
    if headers is None:
        headers = {}
    if accept:
        headers['Accept'] = ','.join(accept)
    else:
        headers['Accept'] = '*/*'
    return headers


def fix_params(params=None):
    if params is None:
        params = {}
    for k in params.keys():
        if not isinstance(k, str):
            new_k = str(k)
            params[new_k] = params[k]
            del params[k]
        else:
            try:
                k = k.encode('ascii')
            except UnicodeEncodeError:
                new_k = k.encode('utf8')
                params[new_k] = params[k]
                del params[k]
            except UnicodeDecodeError:
                pass

    for k in params.keys():
        if not isinstance(params[k], str):
            params[k] = str(params[k])
        try:
            params[k].encode('ascii')
        except UnicodeEncodeError:
            new_v = params[k].encode('utf8')
            params[k] = new_v
        except UnicodeDecodeError:
            pass

    return params


def fix_headers(headers=None):
    if headers is None:
        headers = {}
    for k in headers.keys():
        if not isinstance(k, str):
            new_k = str(k)
            headers[new_k] = headers[k]
            del headers[k]
        if not isinstance(headers[k], str):
            headers[k] = str(headers[k])
        try:
            headers[k].encode('ascii')
            k = k.encode('ascii')
        except UnicodeEncodeError:
            new_k = k.encode('ascii', 'ignore')
            new_v = headers[k].encode('ascii', 'ignore')
            headers[new_k] = new_v
            del headers[k]
    return headers


def fix_files(files=None):
    if files is None:
        files = {}
    # fix keys in files
    for k in files.keys():
        if not isinstance(k, str):
            new_k = str(k)
            files[new_k] = files[k]
            del files[k]
        try:
            k = k.encode('ascii')
        except UnicodeEncodeError:
            new_k = k.encode('utf8')
            files[new_k] = files[k]
            del files[k]
    # second pass to fix filenames
    for k in files.keys():
        try:
            files[k]['filename'].encode('ascii')
        except UnicodeEncodeError:
            files[k]['filename'] = files[k]['filename'].encode('utf8')
    return files


if __name__ == "__main__":
    print(rest_invoke("http://localhost:9090/",
                      method="POST", params={'value': 'store this'},
                      accept=["text/plain", "text/html"], do_async=False))
    image = open('sample.jpg').read()
    r = rest_invoke("http://resizer.ccnmtl.columbia.edu/resize",
                    method="POST",
                    files={'image': {'file': image,
                                     'filename': 'sample.jpg'}},
                    do_async=False)
    out = open("thumb.jpg", "w")
    out.write(r)
    out.close()
    GET("http://resizer.ccnmtl.columbia.edu/")
    r = POST("http://resizer.ccnmtl.columbia.edu/resize",
             files={'image': {'file': image,
                              'filename': 'sample.jpg'}},
             do_async=False)
    # evil unicode tests
    print(rest_invoke(u"http://localhost:9090/foo/",
                      params={u'foo\u2012': u'\u2012'},
                      headers={u"foo\u2012": u"foo\u2012"}))

    r = rest_invoke(u"http://localhost:9090/resize", method="POST",
                    files={u'image\u2012': {'file': image,
                                            'filename': u'samp\u2012le.jpg'}},
                    do_async=False)
