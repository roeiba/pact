.. _user_guide:

User's Guide
============

Creating Pacts
--------------

A *pact* is a form of a promise. It's similar to concepts like A+/promises that you may be familiar with already. It is intended for scenarios where you want to return 'handles' to asynchronous events, and be able to elegantly control what happens with those events.

Suppose we have an API that copies a large directory structure in the background, ``delete_async(path)``, returning some identifier for the ongoing task, and a complementary API, ``is_async_delete_finished(id)`` asking if it completed.

A *pact* wraps this api nicely:

.. code-block:: python

		>>> from pact import Pact

		>>> def pact_delete_async(path):
		...     returned = Pact('Deleting {0}'.format(path))
		...     operation_id = delete_async(path)
		...     returned.until(is_async_delete_finished, operation_id)
		...     return returned
		

Note the example uses :func:`pact.Pact.until` to denote when the pact can be considered 'finished'.

Checking Pact Status
--------------------

Our code can now interact with the returned *pact* object. Checking whether or not a pact is finished can be done using the ``is_finished`` predicate, but it does not cause our pact to actually check its predicates for completion. That is done by ``poll``:

.. code-block:: python

		>>> p = pact_delete_async('/path')
		>>> p.poll()
		False
		>>> p.is_finished()
		False
		>>> sleep(10)
		>>> p.is_finished()
		False
		>>> p.poll()
		True
		>>> p.is_finished()
		True

Waiting on Pacts
----------------

A very common scenario is to wait until a pact is finished. This is what the :func:`pact.Pact.wait` method is for:

.. code-block:: python

		>>> from pact import TimeoutExpired
		>>> p = pact_delete_async('/path')
		>>> p.wait()
		>>> p.is_finished()
		True

You can also set the default timeout for the pact. This is done by using :func:`pact.Pact.set_default_timeout` method:

.. code-block:: python

		>>> p = pact_delete_async('/path')
		>>> p.set_default_timeout(timeout_seconds=5)
		>>> try:
		...     p.wait()
		... except TimeoutExpired as e:
		...     print('Got exception:', e)
		Got exception: Timeout of 5 seconds expired waiting for <Pact: Deleting /path>

Another option is to specify a timeout in seconds, which will override the default. Expiration of the timeout will result in an exception:

.. code-block:: python

		>>> p = pact_delete_async('/path')
		>>> try:
		...     p.wait(timeout_seconds=1.5)
		... except TimeoutExpired as e:
		...     print('Got exception:', e)
		Got exception: Timeout of 1.5 seconds expired waiting for <Pact: Deleting /path>

Grouping Pacts
--------------

Pacts support joining multiple instances together to form a group:

.. code-block:: python
		
		>>> from pact import PactGroup
		>>> p1 = pact_delete_async('/path1')
		>>> p2 = pact_delete_async('/path2')
		>>> group = PactGroup([p1, p2])

There is a shorter syntax as well, using the ``+`` operator:

.. code-block:: python

		>>> group = p1 + p2

The most immediate thing you can do on a pact group is wait for it to end altogether:

.. code-block:: python

		>>> group.wait()

And of course it will be more descriptive when only one pact was not satisfied:

.. code-block:: python

		>>> group =(pact_delete_async('/path1') + pact_delete_async('/huge_directory'))
		>>> try:
		...     group.wait(timeout_seconds=10)
		... except TimeoutExpired as e:
		...     print('Got exception:', e)
		Got exception: Timeout of 10 seconds expired waiting for [<Pact: Deleting /huge_directory>]

Waiting for group is a lazy operation, by default, which means that will poll pacts only if previous pact had finished:

.. code-block:: python

       >>> pact_a = pact_delete_async('/path_a').during(print, 'a', end='').then(print, 'A', end='')
       >>> pact_b = pact_delete_async('/path_b').during(print, 'b', end='').then(print, 'B')
       >>> PactGroup([pact_a, pact_b]).wait()
       aaaaaaaaaaaAbB

Group can be poll eagerly by passing ``lazy=False`` to its creation. This will make each polling operation to poll all unfinished pacts in the group every time.

.. code-block:: python

       >>> pact_a = pact_delete_async('/path_a').during(print, 'a', end='').then(print, 'A', end='')
       >>> pact_b = pact_delete_async('/path_b').during(print, 'b', end='').then(print, 'B')
       >>> PactGroup([pact_a, pact_b], lazy=False).wait()
       ababababababababababaAbB


Absorbing Pacts into Groups
---------------------------

Sometimes you would like to group pacts, but only fire the ``then`` callbacks when the entire group is satisfied. In addition to adding the ``then`` to the group itself, there is another shortcut called ``absorb``:

.. code-block:: python
       
       >>> group = pact_delete_async('/path1').then(print, 'finished') + pact_delete_async('/huge_directory').then(print, 'also finished')

In the above example, the ``also finished`` string will get printed once ``huge_directory`` is deleted. However this may be long before ``/path`` is deleted. To force all ``then`` callbacks to happen after the entire group finishes, we can use ``absorb``:

.. code-block:: python
       
       >>> group = PactGroup()
       >>> p1 = pact_delete_async('/path1').then(print, 'finished') 
       >>> p2 = pact_delete_async('/huge_directory').then(print, 'also finished')
       >>> group.add(p1, absorb=True)
       >>> group.add(p2, absorb=True)

.. note:: When absorbing pacts, the callbacks are no longer owned by the absorbed pacts, so waiting for them alone would not trigger them


Triggering Actions
------------------

You can easily attach callbacks to occur when a pact finishes:

.. code-block:: python
       
       >>> pact_delete_async('/path1').then(print, 'finished').wait()
       finished

This can be chained multiple times

.. code-block:: python
       
       >>> pact_delete_async('/path1').\
       ...    then(print, 'message1').\
       ...    then(print, 'message2').\
       ...    wait()
       message1
       message2

Also for groups:

.. code-block:: python
       
       >>> start_time = time()
       >>> group = pact_delete_async('/path1').\
       ...     then(lambda: print('path1 finished after', time() - start_time, 'seconds')) \
       ...   + pact_delete_async('/huge_dir').\
       ...     then(lambda: print('huge_dir finished after', time() - start_time, 'seconds'))
       >>> group.wait()
       path1 finished after 10.0 seconds
       huge_dir finished after 30.0 seconds


Triggering Actions During a Wait
--------------------------------

You can specify a callback to be called while the wait is ongoing, using :func:`pact.Pact.during`:

.. code-block:: python
       
       >>> pact_delete_async('/path').during(print, '~', end='').then(print, 'Done!').wait()
       ~~~~~~~~~~~Done!

Triggering Actions on Timeout
-----------------------------

Using the :func:`pact.Pact.on_timeout` method, you can add additional callbacks to be called when a timeout is encountered:

.. code-block:: python
       
       >>> pact_delete_async('/path').on_timeout(print, 'bummer').on_timeout(print, 'so what now?').wait()



