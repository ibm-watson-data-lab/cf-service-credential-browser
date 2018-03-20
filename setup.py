from setuptools import setup, find_packages
setup(name='cfservices',
	  version='0.1.0',
	  description='IBM Cloud services credential browser',
	  url='https://github.com/ibm-watson-data-lab/cf-service-credential-browser',
	  install_requires=['pixiedust >= 1.1.9', 'pandas','requests'],
	  author='Patrick Titzler',
	  author_email='ptitzler@us.ibm.com',
	  license='Apache 2.0',
	  packages=find_packages(),
	  include_package_data=False,
	  zip_safe=False,
	  classifiers=[
	   'Development Status :: 4 - Beta',
	   'Programming Language :: Python :: 2.7',
	   'Programming Language :: Python :: 3.5'
	  ],
	  python_requires='>=2.7'
)
