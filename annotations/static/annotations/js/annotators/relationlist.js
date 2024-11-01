RelationListItem = {
    props: ['relation'],
    template: `
        <li v-bind:class="{
                'list-group-item': true,
                'relation-list-item': true,
                'relation-disabled': !isReadyToSubmit
            }"
            :title="!isReadyToSubmit ? 'RelationSet is not ready to submit' : ''">
            <div>
                <input type="checkbox"
                       v-model="isChecked"
                       @change="toggleSelection"
                       :disabled="!isReadyToSubmit" />
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
            console.log('relationset_status:', this.relation);
            return this.relation.status === 'ready_to_submit';
        }
    },
    methods: {
        toggleSelection() {
            this.$emit('toggleSelection', { relation: this.relation, selected: this.isChecked });
        },
        select: function () {
            this.$emit('selectrelation', this.relation);
        },
        isSelected: function () {
            return this.relation.selected;
        },
        getRepresentation: function (relation) {
            if (relation.representation) {
                return relation.representation;
            } else {
                return relation.appellations.map(function (appellation) {
                    return appellation.interpretation.label;
                }).join('; ');
            }
        },
        getCreatorName: function (creator) {
            if (creator.id == USER_ID) {
                return 'you';
            } else {
                return creator.username;
            }
        },
        getFormattedDate: function (isodate) {
            return moment(isodate).format('dddd LL [at] LT');
        },
        toggleSelection() {
            this.$emit('toggleSelection', { relation: this.relation, selected: this.isChecked });
        }
    }
}

// RelationList Component
RelationList = {
    props: ['relations'],
    template: `<div>
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5>Relations</h5>
                        <button class="btn btn-primary btn-sm" 
                                @click="submitSelected" 
                                style="margin: 5px;"
                                :disabled="!canSubmit">
                            <i class="glyphicon glyphicon-send"></i>    
                            Submit Selected Quadruples
                        </button>
                        <button class="btn btn-secondary" @click="toggleSidebar">
                            <span :class="sidebarVisible ? 'glyphicon glyphicon-chevron-left' : 'glyphicon glyphicon-chevron-right'"></span>
                        </button>
                    </div>
                    <div v-show="sidebarVisible">
                        <ul class="list-group relation-list">
                            <relation-list-item
                                v-for="relation in relations"
                                :key="relation.id"
                                :relation="relation"
                                @toggleSelection="toggleSelection">
                            </relation-list-item>
                        </ul>
                    </div>
                </div>`,
    components: {
        'relation-list-item': RelationListItem
    },
    data() {
        return {
            selectedQuadruples: [],
            sidebarVisible: false
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
                this.selectedQuadruples = this.selectedQuadruples.filter(id => id !== quadrupleId);
            })
            .catch((error) => {
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
        },
        toggleSidebar() {
            this.sidebarVisible = !this.sidebarVisible;
        }
    }
};
