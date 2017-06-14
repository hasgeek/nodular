#!/bin/sh
set -e
coverage run `which nosetests`
coverage report
