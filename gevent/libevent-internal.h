struct event_base {
	const void *evsel;
	void *evbase;
	int event_count;		/* counts number of total events */
	int event_count_active;	/* counts number of active events */

	int event_gotterm;		/* Set to terminate loop */
	int event_break;		/* Set to terminate loop immediately */

	/* active event management */
	struct event_list **activequeues;
	int nactivequeues;
};


