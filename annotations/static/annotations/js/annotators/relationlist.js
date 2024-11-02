// RelationListItem Component
const RelationListItem = {
    props: ['relation'],
    template: `
        <li v-bind:class="{
                'list-group-item': true,
                'relation-list-item': true,
                'relation-disabled': !isReadyToSubmit || isAlreadySubmitted
            }"
            :title="tooltipText">
            <div>
                <input type="checkbox"
                       v-model="isChecked"
                       @change="toggleSelection"
                       :disabled="!isReadyToSubmit || isAlreadySubmitted" />
                {{ getRepresentation(relation) }}
            </div>
            <div class="text-warning">
                Created by <strong>{{ getCreatorName(relation.createdBy) }}</strong> on {{ getFormattedDate(relation.created) }}
            </div>
        </li>
    `,
    data() {
        return {
            isChecked: false
        };
    },
    computed: {
        isReadyToSubmit() {
            return this.relation.status === 'ready_to_submit';
        },
        isAlreadySubmitted() {
            return this.relation.status === 'submitted';
        },
        tooltipText() {
            if (this.isAlreadySubmitted) return 'Already submitted';
            if (!this.isReadyToSubmit) return 'Quadruple is not ready to submit';
            return '';
        }
    },
    methods: {
        toggleSelection() {
            if (!this.isAlreadySubmitted) {
                this.$emit('toggleSelection', { relation: this.relation, selected: this.isChecked });
            }
        },
        getRepresentation(relation) {
            if (relation.representation) {
                return relation.representation;
            } else {
                return relation.appellations.map(appellation => appellation.interpretation.label).join('; ');
            }
        },
        getCreatorName(creator) {
            return creator.id == USER_ID ? 'you' : creator.username;
        },
        getFormattedDate(isodate) {
            return moment(isodate).format('dddd LL [at] LT');
        }
    }
};

// RelationList Component
const RelationList = {
    props: ['relations'],
    template: `<div>
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5>Relations</h5>
                        <button class="btn btn-primary btn-sm" @click="submitSelected" style="margin: 5px;" :disabled="!canSubmit">
                            <i class="glyphicon glyphicon-send"></i>    
                            Submit Selected Quadruples
                        </button>
                    </div>
                    <ul class="list-group relation-list">
                        <relation-list-item
                            v-for="relation in relations"
                            :key="relation.id"
                            :relation="relation"
                            @selectRelation="selectRelation"
                            @toggleSelection="toggleSelection">
                        </relation-list-item>
                    </ul>
                </div>`,
    components: {
        'relation-list-item': RelationListItem
    },
    data() {
        return {
            selectedQuadruples: []
        };
    },
    computed: {
        canSubmit() {
            return this.selectedQuadruples.length > 0 && this.selectedQuadruples.every(id => {
                const relation = this.relations.find(rel => rel.id === id);
                return relation && relation.status === 'ready_to_submit';
            });
        }
    },
    methods: {
        selectRelation(relation) {
            this.$emit('selectRelation', relation);
        },
        toggleSelection({ relation, selected }) {
            if (selected) {
                this.selectedQuadruples.push(relation.id);
            } else {
                this.selectedQuadruples = this.selectedQuadruples.filter(id => id !== relation.id);
            }
        },
        submitSelected() {
            if (this.selectedQuadruples.length === 0) {
                alert("No quadruples selected");
                return;
            }

            let submissionPromises = this.selectedQuadruples.map((quadrupleId) => {
                return this.submitQuadruple(quadrupleId);
            });

            Promise.allSettled(submissionPromises).then((results) => {
                let successes = results.filter(r => r.status === 'fulfilled');
                let failures = results.filter(r => r.status === 'rejected');

                if (successes.length > 0) {
                    alert(`${successes.length} quadruple(s) submitted successfully.`);
                }

                if (failures.length > 0) {
                    let errorMessages = failures.map(r => r.reason.message || r.reason);
                    alert(`Failed to submit ${failures.length} quadruple(s):\n${errorMessages.join('\n')}`);
                }

                this.fetchRelations();
            });
        },

        submitQuadruple(quadrupleId) {
            const csrfToken = getCookie('csrftoken');
            const param = { 'pk': quadrupleId };

            return axios.post(`/rest/relationset/submit`, param, {
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-type': 'application/json'
                },
                withCredentials: true,
            })
            .then(() => {
                console.log(`Quadruple submitted successfully`);
                this.selectedQuadruples = this.selectedQuadruples.filter(id => id !== quadrupleId);
            })
            .catch((error) => {
                console.error(`Failed to submit quadruple ${quadrupleId}:`, error);
                throw error.response ? error.response.data.error : 'Unknown error';
            });
        },

        fetchRelations() {
            axios.get('/rest/relation')
                .then(response => {
                    this.relations = response.data;
                })
                .catch(error => {
                    console.error('Failed to fetch relations:', error);
                });
        }
    }
};
