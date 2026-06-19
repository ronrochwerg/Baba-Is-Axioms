(define (domain baba)
  (:requirements :typing :derived-predicates :negative-preconditions :disjunctive-preconditions :conditional-effects :equality)
  (:types thing location direction - object
          text sprite - thing
          noun property operator - text
          
  )

  (:constants
    north south east west - direction
    baba wall flag rock textBlocks - noun
    push stop you win - property
    is - operator
  )


  (:predicates
    (at ?t - thing ?l - location)
    (is-type ?t - thing ?n - noun)
    (connected ?from ?to - location ?dir - direction)

    (blocked ?l - location ?dir - direction) ;blocked from direction
    (open ?l - location ?dir - direction)
    (will-move ?t - thing ?from ?to - location ?dir - direction)
    (has-prop ?n - noun ?p - property)
    (conversion ?n1 - noun ?n2 - noun)
    

    (do-conversion)
    (check-conversion)
    (won)
  )

    ;; winning the level
    (:derived (won)
        (exists (?s1 ?s2 - sprite ?n1 ?n2 - noun ?l - location)
            (and
                (at ?s1 ?l)
                (at ?s2 ?l)
                (is-type ?s1 ?n1)
                (is-type ?s2 ?n2)
                (has-prop ?n1 win)
                (has-prop ?n2 you)
            )
        )
    )
    ;; location where sprite has stop property is blocked
    (:derived (blocked ?l - location ?dir - direction)
        (exists (?t - thing ?n - noun)
            (and
                (at ?t ?l)
                (is-type ?t ?n)
                (has-prop ?n stop)
                (not (has-prop ?n push)) ;; things that are only stop will always block
                (not (has-prop ?n you))
            )
        )
    )

    ;; location where sprite has push property is blocked
    (:derived (blocked ?l - location ?dir - direction)
        (exists (?t - thing ?n - noun)
            (and
                (at ?t ?l)
                (is-type ?t ?n)
                (or
                    (has-prop ?n push) ;; things that are push, or stop with other properties (you)
                    (has-prop ?n stop) ;; will only act as stop if the next location is blocked
                )
                (or
                    (exists (?l2 - location) ;; next location in direction is blocked
                        (and
                            (connected ?l ?l2 ?dir)
                            (blocked ?l2 ?dir)
                        )
                    )
                    (forall (?l2 - location) ;; on an edge
                        (not (connected ?l ?l2 ?dir))
                    )
                )
            )
        )
    )

    ;; location is open if not blocked
    (:derived (open ?l - location ?dir - direction)
        (not (blocked ?l ?dir))
    )

    ;; which you objects will move in a given direction if it is chosen
    (:derived (will-move ?t - thing ?from ?to - location ?dir - direction)
        (exists (?n - noun)
            (and
                (at ?t ?from)
                (is-type ?t ?n)
                (has-prop ?n you)
                (connected ?from ?to ?dir)
                (open ?to ?dir)
            )
        )
    )

    ;; which push objects will move in a given direction if a another object is moving into them
    (:derived (will-move ?t - thing ?from ?to - location ?dir - direction)
        (exists (?n - noun ?l3 - location ?t2 - thing)
            (and
                (at ?t ?from)
                (is-type ?t ?n)
                (has-prop ?n push)
                (connected ?from ?to ?dir)
                (connected ?l3 ?from ?dir)
                (will-move ?t2 ?l3 ?from ?dir)
            )
        )
    )

    ;; text always has push property
    (:derived (has-prop ?n - noun ?p - property)
        (and
            (= ?n textBlocks)
            (= ?p push)
        )
    ) 

    ; vertical property sentences
    (:derived (has-prop ?n - noun ?p - property)
        (exists (?l1 - location ?l2 - location ?l3 - location)
            (and
                (connected ?l1 ?l2 south)
                (connected ?l2 ?l3 south)
                (at ?n ?l1)
                (at is ?l2)
                (at ?p ?l3)
            )
        )
    )

    ; horizontal property sentences
    (:derived (has-prop ?n - noun ?p - property)
        (exists (?l1 - location ?l2 - location ?l3 - location)
            (and
                (connected ?l1 ?l2 east)
                (connected ?l2 ?l3 east)
                (at ?n ?l1)
                (at is ?l2)
                (at ?p ?l3)
            )
        )
    )

    ; vertical conversion sentences
    (:derived (conversion ?n1 - noun ?n2 - noun)
        (exists (?l1 - location ?l2 - location ?l3 - location)
            (and
                (connected ?l1 ?l2 south)
                (connected ?l2 ?l3 south)
                (at ?n1 ?l1)
                (at is ?l2)
                (at ?n2 ?l3)
            )
        )
    )

    ; horizontal conversion sentences
    (:derived (conversion ?n1 - noun ?n2 - noun)
        (exists (?l1 - location ?l2 - location ?l3 - location)
            (and
                (connected ?l1 ?l2 east)
                (connected ?l2 ?l3 east)
                (at ?n1 ?l1)
                (at is ?l2)
                (at ?n2 ?l3)
            )
        )
    )

    ;; derive whether we have to convert nouns or not
    (:derived (do-conversion)
        (and
            (check-conversion)
            (exists (?s - sprite ?n1 ?n2 - noun)
                (and
                    (conversion ?n1 ?n2)
                    (is-type ?s ?n1)
                )
            )
        )
    )

    ;; movement action
    (:action move
        :parameters (?dir - direction)
        :precondition (not (do-conversion)) ;; must convert before next movement
        :effect (and
            (check-conversion) ;; always check for conversions after a movement
            (forall (?t - thing ?from ?to - location)
                (when (will-move ?t ?from ?to ?dir)
                    (and
                        (not (at ?t ?from))
                        (at ?t ?to)
                    )
                )
            )
        )
    )

    ;; convert sprites into other nouns based on sentences
    (:action convert
        :parameters ()
        :precondition (do-conversion) ;; only convert when necessary
        :effect (and
            (not (check-conversion)) ;; allow for movement next action
            (forall (?n1 ?n2 - noun ?s - sprite)
                (when 
                    (and
                        (not (conversion ?n1 ?n1))
                        (conversion ?n1 ?n2)
                        (is-type ?s ?n1)
                    )
                    (and 
                        (not (is-type ?s ?n1))
                        (is-type ?s ?n2)
                    )
                )
            )
        )
    )
    
    
)
